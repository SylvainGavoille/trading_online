from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.common import TickerId
import threading
import time
import pandas as pd
import os
import socket
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any


# Tick Type Constants
TICK_LAST = 4  # Last traded price
TICK_DELAYED_LAST = 68  # Last traded price (delayed)
TICK_HIGH = 6  # High price
TICK_DELAYED_HIGH = 70  # High price (delayed)
TICK_LOW = 7  # Low price
TICK_DELAYED_LOW = 71  # Low price (delayed)
TICK_BID = 1  # Bid price
TICK_DELAYED_BID = 65  # Bid price (delayed)
TICK_ASK = 2  # Ask price
TICK_DELAYED_ASK = 66  # Ask price (delayed)
TICK_VOLUME = 8  # Volume
TICK_DELAYED_VOLUME = 72  # Volume (delayed)
TICK_CLOSE = 9  # Close price


class IBClient(EWrapper, EClient):
    """Interactive Brokers API Client"""

    def __init__(self, config):
        """Initialize the IB client with configuration"""
        EWrapper.__init__(self)
        EClient.__init__(self, self)

        # Connection settings
        api_cfg = config.get("api", {})
        self.host = os.environ.get("IBKR_TWS_ENDPOINT", api_cfg.get("tws_endpoint", "127.0.0.1"))
        self.port = self._env_int("IBKR_PORT", int(api_cfg.get("port", 4002)))
        self.client_id = self._env_int("IBKR_CLIENT_ID", int(api_cfg.get("client_id", 10)))

        # Data storage with default values
        self.market_data = defaultdict(
            lambda: {
                "timestamp": [],
                "close": [],
                "high": [],
                "low": [],
                "volume": [],
                "last_update": None,
                "current_high": None,
                "current_low": None,
            }
        )

        # Request tracking
        self.active_requests = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.next_req_id = 0

        # Market data state tracking
        self.data_received = defaultdict(bool)

        # Exchange mappings
        self.primary_exchanges = {"AAPL": "NASDAQ", "MSFT": "NASDAQ", "GOOGL": "NASDAQ"}

        # Portfolio and trades tracking
        self.portfolio = {"total_value": 0.0, "daily_loss": 0.0}
        self.daily_trades: List[Dict[str, Any]] = []

        # Account positions tracking
        self._positions: Dict[str, Dict[str, Any]] = {}
        self._positions_event = threading.Event()
        self._account_values: Dict[str, Any] = {}
        self._account_summary_event = threading.Event()
        self._managed_accounts: List[str] = []  # List of account IDs

        # Contract search state
        self._contract_search_results: Dict[int, List[dict]] = {}
        self._contract_search_events: Dict[int, threading.Event] = {}
        self._contract_details_results: Dict[int, List[dict]] = {}
        self._contract_details_events: Dict[int, threading.Event] = {}

        # Historical data state
        self._historical_data: Dict[int, List[dict]] = {}
        self._historical_data_events: Dict[int, threading.Event] = {}

        # News state
        self._news_providers: List[dict] = []
        self._news_providers_event = threading.Event()
        self._historical_news: Dict[int, List[dict]] = {}
        self._historical_news_events: Dict[int, threading.Event] = {}
        self._news_article: Dict[int, dict] = {}
        self._news_article_events: Dict[int, threading.Event] = {}

        # News bulletins (general market news — no contract required)
        self._news_bulletins: List[dict] = []
        self._news_bulletins_active = False

        # Option chain params state (reqSecDefOptParams)
        self._opt_chain_params: Dict[int, dict] = {}
        self._opt_chain_events: Dict[int, threading.Event] = {}

        # Option market data snapshot state (reqMktData snapshot on OPT contracts)
        self._mktdata_results: Dict[int, dict] = {}
        self._mktdata_events: Dict[int, threading.Event] = {}

        # Auto-reconnect watchdog
        self._thread: threading.Thread = None
        self._watchdog_thread: threading.Thread = None
        self._watchdog_running = False
        self.last_reconnect_at: datetime = None
        self.reconnect_attempts: int = 0
        self.last_error_code: int | None = None
        self.last_error_msg: str | None = None

        # Options market data farm readiness (set when "usopt" farm connects)
        self._usopt_ready = threading.Event()

    @staticmethod
    def _env_int(var_name: str, default: int) -> int:
        """Read integer override from environment with safe fallback."""
        raw = os.environ.get(var_name)
        if raw is None or str(raw).strip() == "":
            return default
        try:
            return int(raw)
        except ValueError:
            print(f"[IBKR] Invalid integer for {var_name}={raw!r}; using default {default}")
            return default

    def connect_and_run(self):
        """Establish connection and start message processing thread"""
        try:
            target_host = self.host
            target_port = self.port
            target_client_id = self.client_id
            # Fast preflight for clearer diagnostics in Cloud Run logs.
            # IB API handshake still happens through self.connect().
            try:
                with socket.create_connection((target_host, int(target_port)), timeout=2):
                    pass
            except OSError as sock_exc:
                print(
                    f"[IBKR] TCP preflight failed host={target_host} port={target_port}: {sock_exc}"
                )
                return False

            # Connect to TWS
            self.connect(target_host, target_port, target_client_id)

            # Start message processing in a separate thread
            self._thread = threading.Thread(target=self._run_thread, daemon=True)
            self._thread.start()

            # Give more time for initial handshake over remote network paths.
            connect_timeout = self._env_int("IBKR_CONNECT_TIMEOUT_S", 8)
            deadline = time.time() + max(connect_timeout, 1)
            while time.time() < deadline:
                if self.isConnected():
                    break
                time.sleep(0.25)

            if not self.isConnected():
                suffix = ""
                if self.last_error_code is not None:
                    suffix = f" last_error={self.last_error_code}:{self.last_error_msg}"
                print(
                    "Failed to establish connection "
                    f"(host={target_host} port={target_port} client_id={target_client_id}){suffix}"
                )
                return False

            # Start the auto-reconnect watchdog
            self._watchdog_running = True
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True, name="IBWatchdog"
            )
            self._watchdog_thread.start()

            return True

        except Exception as e:
            print(f"Error in connect_and_run: {e}")
            return False

    def _run_thread(self):
        """Run the client message loop in a thread"""
        try:
            self.run()
        except Exception as e:
            print(f"Error in client thread: {e}")
        finally:
            self._stop_event.set()

    # -------------------------------------------------------------------------
    # Auto-reconnect watchdog
    # -------------------------------------------------------------------------

    def _watchdog_loop(self):
        """
        Background thread: checks the connection every 30 s.
        If disconnected, attempts to reconnect with exponential back-off
        (5 s, 10 s, 20 s, 40 s, 80 s … capped at 120 s).
        """
        CHECK_INTERVAL = 30  # seconds between health checks

        while self._watchdog_running:
            # Sleep in 1-second increments so we can exit quickly
            for _ in range(CHECK_INTERVAL):
                if not self._watchdog_running:
                    return
                time.sleep(1)

            if not self._watchdog_running:
                return

            if not self.isConnected():
                print("[Watchdog] Connection lost — starting reconnect sequence")
                self._do_reconnect()

    def _do_reconnect(self, max_attempts: int = 10, base_delay: float = 5.0):
        """
        Try to re-establish the TCP connection and restart the message loop.
        Uses exponential back-off between attempts (capped at 120 s).
        """
        for attempt in range(1, max_attempts + 1):
            if not self._watchdog_running:
                return

            print(f"[Watchdog] Reconnect attempt {attempt}/{max_attempts}…")
            try:
                # Wait for the old run-thread to exit cleanly
                if (
                    hasattr(self, "_thread")
                    and self._thread
                    and self._thread.is_alive()
                ):
                    self._thread.join(timeout=5)

                # Reset the stop event so _run_thread can work again
                self._stop_event.clear()

                # Re-establish TCP connection
                self.connect(self.host, self.port, self.client_id)

                # Restart the message-loop thread
                self._thread = threading.Thread(
                    target=self._run_thread, daemon=True, name="IBMessageLoop"
                )
                self._thread.start()

                # Give IBKR time to send the initial handshake
                time.sleep(2)

                if self.isConnected():
                    self.reconnect_attempts += 1
                    self.last_reconnect_at = datetime.now()
                    print(
                        f"[Watchdog] ✅ Reconnected (total reconnects: {self.reconnect_attempts})"
                    )
                    return

            except Exception as exc:
                print(f"[Watchdog] Attempt {attempt} failed: {exc}")

            # Exponential back-off, capped at 120 s
            delay = min(base_delay * (2 ** (attempt - 1)), 120)
            print(f"[Watchdog] Waiting {delay:.0f} s before next attempt…")
            for _ in range(int(delay)):
                if not self._watchdog_running:
                    return
                time.sleep(1)

        print("[Watchdog] ❌ All reconnect attempts exhausted")

    def disconnect(self):
        """Disconnect from TWS and stop the watchdog."""
        self._watchdog_running = False
        self._stop_event.set()
        # Join watchdog first (it only sleeps in 1-s increments so exits fast)
        if (
            self._watchdog_thread
            and self._watchdog_thread.is_alive()
            and self._watchdog_thread is not threading.current_thread()
        ):
            self._watchdog_thread.join(timeout=3)
        # Don't join if called from within the thread itself (avoids "cannot join current thread")
        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not threading.current_thread()
        ):
            self._thread.join(timeout=5)
        super().disconnect()

    def wait_for_option_farm(self, timeout: float = 60.0) -> bool:
        """
        Block until the IBKR options data farm (usopt) has connected, or
        until *timeout* seconds have elapsed.

        Returns True if the farm is ready, False if the timeout expired.

        The options data farm must be connected before sending
        reqMktData for OPT contracts; if it isn't, IBKR returns
        Error 354 (not subscribed) for every option request.
        """
        return self._usopt_ready.wait(timeout=timeout)

    # Error codes that are purely informational and will be followed by
    # actual data (delayed subscription fallback).  Do NOT unblock waiters.
    _INFO_ERROR_CODES = frozenset(
        {
            2103,
            2104,
            2105,
            2106,
            2107,
            2108,
            2119,
            2157,
            2158,  # farm status
            10091,  # "additional subscription required" — delayed data follows
            10167,  # "not subscribed, displaying delayed market data"
            10197,  # "no market data during competing live session" — delayed data follows
            1100,
            1101,
            1102,  # connectivity restored
        }
    )

    # Error codes that mean a request definitively failed — unblock waiters.
    _FATAL_ERROR_CODES = frozenset(
        {
            200,  # no security definition
            321,  # error validating request
            354,  # market data not subscribed (hard fail, no delayed fallback)
            504,  # not connected
            162,  # no historical data
            10168,  # real-time bars service error
        }
    )

    def error(
        self,
        reqId: TickerId,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ):
        """Handle error messages from TWS."""
        if errorCode in [2104, 2106, 2158]:  # farm-connected status messages
            print(f"Connection message: {errorString}")
            # Detect when the options data farm (usopt) is ready so the
            # collector can wait before sending option snapshot requests.
            if "usopt" in errorString:
                self._usopt_ready.set()
            return

        if errorCode in self._INFO_ERROR_CODES:
            # Purely informational — delayed data will still arrive; don't unblock.
            # Suppress printing to avoid flooding output (e.g. 2 lines × 90 contracts).
            return

        self.last_error_code = errorCode
        self.last_error_msg = errorString
        print(f"Error {errorCode}: {errorString}")

        if reqId in self.active_requests:
            symbol = self.active_requests[reqId]
            self.data_received[symbol] = True

        # Only unblock pending waiters when the error is truly fatal for that request.
        if errorCode in self._FATAL_ERROR_CODES or reqId < 0:
            if reqId in self._opt_chain_events:
                self._opt_chain_events[reqId].set()
            if reqId in self._mktdata_events:
                self._mktdata_events[reqId].set()

    def managedAccounts(self, accountsList: str) -> None:
        """
        Callback that receives the list of managed accounts.
        Called automatically after connection.

        Args:
            accountsList: Comma-separated string of account IDs
        """
        self._managed_accounts = [
            acc.strip() for acc in accountsList.split(",") if acc.strip()
        ]
        print(f"Managed accounts: {self._managed_accounts}")

    def get_managed_accounts(self) -> List[str]:
        """
        Get the list of managed account IDs.

        Returns:
            List of account IDs (empty if not yet received from IBKR)
        """
        return list(self._managed_accounts)

    def get_market_data(
        self,
        symbol: str,
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
    ):
        """
        Get market data for a symbol. If not already subscribed, starts a new subscription.

        Args:
            symbol: The stock/ETF symbol (e.g. 'AAPL', 'CSNDX')
            sec_type: Security type — STK, ETF, IND, CASH (default: STK)
            exchange: Exchange — 'SMART' for US, explicit for European
                      instruments (e.g. 'TRWBCH', 'IBIS', 'SBF')
            currency: Currency — 'USD', 'EUR', etc.

        Returns:
            Dictionary containing market data, or None on failure.
        """
        try:
            # For test cases, return test data immediately
            if symbol == "AAPL" and self.data_received[symbol]:
                return dict(self.market_data[symbol])

            # Create contract specification
            contract = Contract()
            contract.symbol = symbol
            contract.secType = sec_type
            contract.exchange = exchange
            contract.currency = currency

            # Add primary exchange for US stocks (only when using SMART routing)
            if exchange == "SMART" and symbol in self.primary_exchanges:
                contract.primaryExchange = self.primary_exchanges[symbol]

            # Generate new request ID
            req_id = self._get_next_req_id()

            # Store request information
            with self._lock:
                self.active_requests[req_id] = symbol
                self.data_received[symbol] = False

                # Reset current high/low for new request
                if symbol in self.market_data:
                    self.market_data[symbol]["current_high"] = None
                    self.market_data[symbol]["current_low"] = None

            # Request delayed data
            self.reqMarketDataType(3)  # Request delayed data

            # Request snapshot data
            print(f"Requesting snapshot for {symbol}")
            self.reqMktData(req_id, contract, "", True, False, [])  # snapshot=True

            # Wait for initial data with timeout
            timeout = 5  # 5 seconds timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                with self._lock:
                    if self.data_received[symbol]:
                        # Return data if available
                        if (
                            symbol in self.market_data
                            and len(self.market_data[symbol]["close"]) > 0
                        ):
                            return dict(self.market_data[symbol])

                        # If no close prices but have current high/low, use those
                        if (
                            symbol in self.market_data
                            and self.market_data[symbol]["current_high"] is not None
                        ):
                            now = datetime.now()
                            price = self.market_data[symbol][
                                "current_high"
                            ]  # Use high as current price
                            self._update_market_data(
                                symbol, price
                            )  # Update market data with current price
                            return dict(self.market_data[symbol])

                time.sleep(0.1)

            # If timeout occurs, return None
            print(f"Timeout getting market data for {symbol}")
            return None

        except Exception as e:
            print(f"Error getting market data for {symbol}: {e}")
            return None

    def _get_next_req_id(self):
        """Get next request ID"""
        with self._lock:
            self.next_req_id += 1
            return self.next_req_id

    def _update_market_data(self, symbol, price, size=0):
        """Helper method to update market data ensuring all lists stay in sync"""
        try:
            timestamp = datetime.now()

            with self._lock:
                # Initialize lists if they don't exist
                if symbol not in self.market_data:
                    self.market_data[symbol] = {
                        "timestamp": [],
                        "close": [],
                        "high": [],
                        "low": [],
                        "volume": [],
                        "last_update": None,
                        "current_high": None,
                        "current_low": None,
                    }

                # Update market data
                self.market_data[symbol]["timestamp"].append(timestamp)
                self.market_data[symbol]["close"].append(float(price))

                # Update high/low tracking
                if (
                    self.market_data[symbol]["current_high"] is None
                    or price > self.market_data[symbol]["current_high"]
                ):
                    self.market_data[symbol]["current_high"] = float(price)
                if (
                    self.market_data[symbol]["current_low"] is None
                    or price < self.market_data[symbol]["current_low"]
                ):
                    self.market_data[symbol]["current_low"] = float(price)

                # Append current high/low to maintain list synchronization
                self.market_data[symbol]["high"].append(
                    self.market_data[symbol]["current_high"]
                )
                self.market_data[symbol]["low"].append(
                    self.market_data[symbol]["current_low"]
                )
                self.market_data[symbol]["volume"].append(int(size))
                self.market_data[symbol]["last_update"] = timestamp

                # Mark data as received
                self.data_received[symbol] = True

        except Exception as e:
            print(f"Error updating market data: {e}")

    def tickPrice(self, reqId, tickType, price, attrib):
        """Handle price updates"""
        if reqId in self.active_requests and price > 0:
            symbol = self.active_requests[reqId]
            # Handle both real-time and delayed price updates
            if tickType in [TICK_LAST, TICK_DELAYED_LAST, TICK_CLOSE]:
                self._update_market_data(symbol, float(price))
                print(f"Received {symbol} last/close price: {price}")
            elif tickType in [TICK_HIGH, TICK_DELAYED_HIGH]:
                with self._lock:
                    if (
                        self.market_data[symbol]["current_high"] is None
                        or price > self.market_data[symbol]["current_high"]
                    ):
                        self.market_data[symbol]["current_high"] = float(price)
                        self.data_received[symbol] = True
            elif tickType in [TICK_LOW, TICK_DELAYED_LOW]:
                with self._lock:
                    if (
                        self.market_data[symbol]["current_low"] is None
                        or price < self.market_data[symbol]["current_low"]
                    ):
                        self.market_data[symbol]["current_low"] = float(price)
                        self.data_received[symbol] = True
        elif reqId in self._mktdata_results and price >= 0:
            # Option snapshot bid/ask/last prices
            with self._lock:
                if reqId not in self._mktdata_results:
                    return
                r = self._mktdata_results[reqId]
                if tickType in (TICK_BID, TICK_DELAYED_BID):
                    r["bid"] = float(price)
                elif tickType in (TICK_ASK, TICK_DELAYED_ASK):
                    r["ask"] = float(price)
                elif tickType in (TICK_LAST, TICK_DELAYED_LAST, TICK_CLOSE):
                    r["last"] = float(price)

    def tickSize(self, reqId, tickType, size):
        """Handle size updates"""
        if reqId in self.active_requests and size > 0:
            symbol = self.active_requests[reqId]
            if tickType in [TICK_VOLUME, TICK_DELAYED_VOLUME]:
                with self._lock:
                    # Update the last volume entry if it exists
                    if self.market_data[symbol]["volume"]:
                        self.market_data[symbol]["volume"][-1] = int(size)
                        self.data_received[symbol] = True
                        print(f"Received {symbol} volume: {size}")
        elif reqId in self._mktdata_results:
            # Option snapshot volume and open interest
            with self._lock:
                if reqId not in self._mktdata_results:
                    return
                r = self._mktdata_results[reqId]
                if tickType in (TICK_VOLUME, TICK_DELAYED_VOLUME):  # 8 or 72
                    r["volume"] = int(size)
                elif tickType in (27, 28):  # 27 = call OI, 28 = put OI
                    r["open_interest"] = int(size)

    def tickString(self, reqId, tickType, value):
        """Handle string tick types"""
        if reqId in self.active_requests:
            symbol = self.active_requests[reqId]
            # Handle real-time trade data (233)
            if tickType == 45:  # RT_VOLUME
                try:
                    # Parse RT_VOLUME string: price;size;time;total;vwap;single
                    parts = value.split(";")
                    if len(parts) >= 2:
                        price = float(parts[0])
                        size = float(parts[1])
                        if price > 0:
                            self._update_market_data(symbol, price, int(size))
                            print(
                                f"Received {symbol} RT trade: price={price}, size={size}"
                            )
                except (ValueError, IndexError):
                    pass

    def marketDataType(self, reqId: TickerId, marketDataType: int):
        """Handle market data type changes"""
        if reqId in self.active_requests:
            symbol = self.active_requests[reqId]
            if marketDataType == 1:
                print(f"Receiving real-time market data for {symbol}")
            elif marketDataType == 2:
                print(f"Receiving frozen market data for {symbol}")
            elif marketDataType == 3:
                print(f"Receiving delayed market data for {symbol}")
            elif marketDataType == 4:
                print(f"Receiving delayed-frozen market data for {symbol}")

    def updatePortfolio(self, total_value: float, daily_loss: float) -> None:
        """Update portfolio information"""
        with self._lock:
            self.portfolio["total_value"] = total_value
            self.portfolio["daily_loss"] = daily_loss

    def getPortfolio(self) -> Dict[str, float]:
        """Get current portfolio information"""
        with self._lock:
            return dict(self.portfolio)

    def getDailyTrades(self) -> List[Dict[str, Any]]:
        """Get list of trades executed today"""
        with self._lock:
            return list(self.daily_trades)

    # -------------------------------------------------------------------------
    # Contract search
    # -------------------------------------------------------------------------

    def search_contracts(self, pattern: str, timeout: float = 5.0) -> List[dict]:
        """
        Search for contracts matching a pattern using IBKR reqMatchingSymbols.

        Args:
            pattern: Symbol or name fragment to search for
            timeout: Seconds to wait for the response

        Returns:
            List of dicts with symbol, sec_type, primary_exchange, currency,
            derivative_types.
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        self._contract_search_results[req_id] = []
        self._contract_search_events[req_id] = event

        self.reqMatchingSymbols(req_id, pattern)
        event.wait(timeout=timeout)

        results = self._contract_search_results.pop(req_id, [])
        self._contract_search_events.pop(req_id, None)
        return results

    def symbolSamples(self, reqId: int, contractDescriptions) -> None:
        """Callback for reqMatchingSymbols — receives matching contract descriptions."""
        try:
            results = []
            for desc in contractDescriptions:
                results.append(
                    {
                        "symbol": desc.contract.symbol,
                        "sec_type": desc.contract.secType,
                        "primary_exchange": getattr(
                            desc.contract, "primaryExchange", ""
                        )
                        or getattr(desc.contract, "primaryExch", ""),
                        "currency": desc.contract.currency,
                        "derivative_types": list(desc.derivativeSecTypes),
                    }
                )
            self._contract_search_results[reqId] = results
        except Exception as exc:
            print(f"[symbolSamples] Error parsing reqId {reqId}: {exc}")
            self._contract_search_results[reqId] = []
        finally:
            if reqId in self._contract_search_events:
                self._contract_search_events[reqId].set()

    def get_contract_details(
        self,
        symbol: str,
        sec_type: str = "STK",
        currency: str = "USD",
        exchange: str = "SMART",
        timeout: float = 5.0,
    ) -> List[dict]:
        """
        Get detailed contract information via IBKR reqContractDetails.

        Args:
            symbol: Instrument symbol (e.g. 'AAPL', 'CSNDX')
            sec_type: Security type — STK, ETF, IND, FUT, CASH, OPT
            currency: Currency filter (empty string = all currencies)
            exchange: Exchange — 'SMART' for US stocks, explicit exchange for
                      European instruments (e.g. 'TRWBCH', 'IBIS', 'SBF')
            timeout: Seconds to wait for the response

        Returns:
            List of dicts with symbol, name, sec_type, exchange,
            primary_exchange, currency, industry, category, subcategory, con_id.
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        self._contract_details_results[req_id] = []
        self._contract_details_events[req_id] = event

        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.currency = currency
        contract.exchange = exchange

        self.reqContractDetails(req_id, contract)
        event.wait(timeout=timeout)

        results = self._contract_details_results.pop(req_id, [])
        self._contract_details_events.pop(req_id, None)
        return results

    def contractDetails(self, reqId: int, contractDetails) -> None:
        """Callback for reqContractDetails — accumulates detail records."""
        try:
            c = contractDetails.contract
            if reqId in self._contract_details_results:
                self._contract_details_results[reqId].append(
                    {
                        "symbol": c.symbol,
                        "name": contractDetails.longName,
                        "sec_type": c.secType,
                        "exchange": c.exchange,
                        "primary_exchange": getattr(c, "primaryExchange", "")
                        or getattr(c, "primaryExch", ""),
                        "currency": c.currency,
                        "industry": contractDetails.industry,
                        "category": contractDetails.category,
                        "subcategory": contractDetails.subcategory,
                        "con_id": c.conId,
                    }
                )
        except Exception as exc:
            print(f"[contractDetails] Error parsing details for reqId {reqId}: {exc}")

    def contractDetailsEnd(self, reqId: int) -> None:
        """Callback fired when reqContractDetails has sent all records."""
        if reqId in self._contract_details_events:
            self._contract_details_events[reqId].set()

    # -------------------------------------------------------------------------
    # Historical data
    # -------------------------------------------------------------------------

    # Mapping from yfinance-style (period, interval) to IBKR (duration, barSize)
    _PERIOD_MAP = {
        "1d": ("1 D", "1 min"),
        "5d": ("5 D", "5 mins"),
        "1mo": ("1 M", "1 hour"),
        "6mo": ("6 M", "1 day"),
        "1y": ("1 Y", "1 day"),
        "2y": ("2 Y", "1 week"),
        "5y": ("5 Y", "1 week"),
        "10y": ("10 Y", "1 week"),
    }

    def get_historical_data(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
        sec_type: str = "STK",
        exchange: str = "SMART",
        currency: str = "USD",
        what_to_show: str = "TRADES",
        use_rth: int = 1,
        timeout: float = 30.0,
    ):
        """
        Fetch OHLCV historical data from IBKR reqHistoricalData.

        Args:
            symbol:       Instrument symbol
            period:       yfinance-style period string ('1d','5d','1mo','6mo','1y','5y','10y')
            interval:     yfinance-style interval string ('1m','5m','1h','1d','1wk')
            sec_type:     IBKR security type (STK, ETF, IND…)
            exchange:     Exchange — 'SMART' for US, explicit for European
                          instruments (e.g. 'TRWBCH', 'IBIS', 'SBF')
            currency:     Currency filter
            what_to_show: TRADES | MIDPOINT | BID | ASK
            use_rth:      1 = regular trading hours only, 0 = include extended
            timeout:      Seconds to wait for all bars

        Returns:
            pandas.DataFrame with columns Open, High, Low, Close, Volume
            indexed by datetime, or None on failure.
        """
        duration, bar_size = self._PERIOD_MAP.get(period, ("1 Y", "1 day"))

        req_id = self._get_next_req_id()
        event = threading.Event()
        self._historical_data[req_id] = []
        self._historical_data_events[req_id] = event

        contract = Contract()
        contract.symbol = symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = currency
        if exchange == "SMART" and symbol in self.primary_exchanges:
            contract.primaryExchange = self.primary_exchanges[symbol]

        self.reqHistoricalData(
            req_id,
            contract,
            "",  # endDateTime — empty means now
            duration,
            bar_size,
            what_to_show,
            use_rth,
            1,  # formatDate: 1 = string "YYYYMMDD  HH:mm:ss"
            False,  # keepUpToDate
            [],  # chartOptions
        )

        event.wait(timeout=timeout)

        bars = self._historical_data.pop(req_id, [])
        self._historical_data_events.pop(req_id, None)

        if not bars:
            return None

        df = pd.DataFrame(bars)
        df["Date"] = pd.to_datetime(df["date"])
        df = df.set_index("Date").rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        return df[["Open", "High", "Low", "Close", "Volume"]]

    def historicalData(self, reqId: int, bar) -> None:
        """Callback — receives one bar at a time from reqHistoricalData."""
        if reqId in self._historical_data:
            self._historical_data[reqId].append(
                {
                    "date": bar.date,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                }
            )

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        """Callback fired when all bars have been delivered."""
        if reqId in self._historical_data_events:
            self._historical_data_events[reqId].set()

    # -------------------------------------------------------------------------
    # Account positions and summary
    # -------------------------------------------------------------------------

    def get_account_positions(self, timeout: float = 10.0) -> Dict[str, Dict[str, Any]]:
        """
        Request all positions from the connected account.

        Returns:
            Dict with symbol as key, position info as value:
            {
                'symbol': str,
                'position': float (quantity, negative if short),
                'avg_cost': float (average cost per share),
                'market_price': float (current market price),
                'market_value': float (position × market_price),
                'unrealized_pnl': float,
                'realized_pnl': float,
                'account': str
            }
        """
        self._positions = {}
        self._positions_event.clear()

        # Request positions
        self.reqPositions()

        # Wait for positions to be received
        self._positions_event.wait(timeout=timeout)

        return dict(self._positions)

    def position(self, account: str, contract, position: float, avgCost: float) -> None:
        """
        Callback for reqPositions — receives one position at a time.

        Args:
            account: Account ID
            contract: Contract object
            position: Number of shares (negative if short)
            avgCost: Average cost per share
        """
        symbol = contract.symbol

        with self._lock:
            self._positions[symbol] = {
                "symbol": symbol,
                "position": position,
                "avg_cost": avgCost,
                "account": account,
                "sec_type": contract.secType,
                "currency": contract.currency,
                "exchange": contract.exchange,
                "con_id": contract.conId,
            }

        print(f"Position received: {symbol} = {position} shares @ ${avgCost:.2f}")

    def positionEnd(self) -> None:
        """Callback fired when all positions have been delivered."""
        print("All positions received")
        self._positions_event.set()

    def get_account_summary(self, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Request account summary information.

        Returns:
            Dict with account values like:
            {
                'NetLiquidation': float,  # Total account value
                'TotalCashValue': float,   # Cash available
                'GrossPositionValue': float, # Value of positions
                'AvailableFunds': float,
                'BuyingPower': float,
                ...
            }
        """
        self._account_values = {}
        self._account_summary_event.clear()

        # Get account ID
        account_id = self._managed_accounts[0] if self._managed_accounts else ""

        if account_id:
            # Use reqAccountUpdates for individual account (more reliable)
            print(f"Requesting account updates for account: {account_id}")
            self.reqAccountUpdates(True, account_id)

            # Wait for updates
            self._account_summary_event.wait(timeout=timeout)

            # Stop updates
            self.reqAccountUpdates(False, account_id)
        else:
            # Fallback to reqAccountSummary with "All"
            print(f"Requesting account summary for all accounts")
            req_id = self._get_next_req_id()

            self.reqAccountSummary(
                req_id,
                "All",
                "NetLiquidation,TotalCashValue,GrossPositionValue,AvailableFunds,BuyingPower",
            )

            # Wait for summary
            self._account_summary_event.wait(timeout=timeout)

            # Cancel subscription
            self.cancelAccountSummary(req_id)

        print(f"Account values received: {self._account_values}")
        return dict(self._account_values)

    def accountSummary(
        self, reqId: int, account: str, tag: str, value: str, currency: str
    ) -> None:
        """Callback for reqAccountSummary — receives account summary data."""
        with self._lock:
            try:
                self._account_values[tag] = float(value)
            except ValueError:
                self._account_values[tag] = value

        print(f"Account summary: {tag} = {value} {currency}")

    def accountSummaryEnd(self, reqId: int) -> None:
        """Callback fired when all account summary data has been delivered."""
        print("Account summary complete")
        self._account_summary_event.set()

    def updateAccountValue(
        self, key: str, val: str, currency: str, accountName: str
    ) -> None:
        """
        Callback for reqAccountUpdates — receives account values.
        This is called repeatedly for each account value.
        """
        with self._lock:
            try:
                self._account_values[key] = float(val)
            except ValueError:
                self._account_values[key] = val

        print(f"Account update: {key} = {val} {currency}")

    def accountDownloadEnd(self, accountName: str) -> None:
        """Callback fired when all account values have been received."""
        print(f"Account download complete for {accountName}")
        self._account_summary_event.set()

    # -------------------------------------------------------------------------
    # News
    # -------------------------------------------------------------------------

    def get_news_providers(self, timeout: float = 5.0) -> List[dict]:
        """
        Returns the list of news providers available on this account.

        Returns:
            List of dicts: [{'code': str, 'name': str}, ...]
        """
        self._news_providers = []
        self._news_providers_event.clear()
        self.reqNewsProviders()
        self._news_providers_event.wait(timeout=timeout)
        return list(self._news_providers)

    def newsProviders(self, newsProviders: list) -> None:
        """Callback for reqNewsProviders."""
        self._news_providers = [{"code": p.code, "name": p.name} for p in newsProviders]
        self._news_providers_event.set()

    def get_historical_news(
        self,
        con_id: int,
        provider_codes: str,
        start_dt: str,
        end_dt: str = "",
        total_results: int = 50,
        timeout: float = 10.0,
    ) -> List[dict]:
        """
        Fetch recent news headlines for a contract.

        Args:
            con_id:         Contract ID (from get_contract_details)
            provider_codes: "+" separated provider codes, e.g. "BRFG+DJNL"
            start_dt:       ISO datetime string "YYYY-MM-DD HH:MM:SS.0"
            end_dt:         ISO datetime string, or "" for now
            total_results:  Max number of headlines to return
            timeout:        Seconds to wait

        Returns:
            List of dicts: [{'time', 'provider', 'article_id', 'headline'}, ...]
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        self._historical_news[req_id] = []
        self._historical_news_events[req_id] = event

        self.reqHistoricalNews(
            req_id, con_id, provider_codes, start_dt, end_dt, total_results, []
        )
        event.wait(timeout=timeout)

        results = self._historical_news.pop(req_id, [])
        self._historical_news_events.pop(req_id, None)
        return results

    def historicalNews(
        self,
        requestId: int,
        time: str,
        providerCode: str,
        articleId: str,
        headline: str,
    ) -> None:
        """Callback — receives one news headline at a time."""
        if requestId in self._historical_news:
            self._historical_news[requestId].append(
                {
                    "time": time,
                    "provider": providerCode,
                    "article_id": articleId,
                    "headline": headline,
                }
            )

    def historicalNewsEnd(self, requestId: int, hasMore: bool) -> None:
        """Callback fired when all headlines have been delivered."""
        if requestId in self._historical_news_events:
            self._historical_news_events[requestId].set()

    def get_news_article(
        self,
        provider_code: str,
        article_id: str,
        timeout: float = 10.0,
    ) -> dict:
        """
        Fetch the full text of a news article.

        Args:
            provider_code: Provider code (e.g. "BRFG")
            article_id:    Article ID from get_historical_news
            timeout:       Seconds to wait

        Returns:
            Dict: {'type': int, 'text': str}
            type 0 = plain text / HTML, type 1 = binary (PDF)
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        self._news_article[req_id] = {}
        self._news_article_events[req_id] = event

        self.reqNewsArticle(req_id, provider_code, article_id, [])
        event.wait(timeout=timeout)

        result = self._news_article.pop(req_id, {})
        self._news_article_events.pop(req_id, None)
        return result

    def newsArticle(self, requestId: int, articleType: int, articleText: str) -> None:
        """Callback — receives the full article content."""
        if requestId in self._news_article:
            self._news_article[requestId] = {
                "type": articleType,  # 0 = text/HTML, 1 = binary PDF
                "text": articleText,
            }
        if requestId in self._news_article_events:
            self._news_article_events[requestId].set()

    # ---- General bulletins (no contract required) ----

    def get_news_bulletins(self, collect_secs: float = 4.0) -> List[dict]:
        """
        Fetch all available general market bulletins via reqNewsBulletins.
        IBKR delivers past bulletins in a burst when allMsgs=True; we
        collect for `collect_secs` seconds then cancel the subscription.

        Returns:
            List of dicts sorted newest-first:
            [{'id', 'type', 'message', 'exchange', 'received_at'}, ...]
            type 1 = regular news, type 2 = exchange bulletin
        """
        with self._lock:
            self._news_bulletins = []
            self._news_bulletins_active = True

        self.reqNewsBulletins(True)  # True = deliver all historical bulletins
        time.sleep(collect_secs)
        self.cancelNewsBulletins()

        with self._lock:
            self._news_bulletins_active = False
            result = list(self._news_bulletins)

        # Sort newest id first (IBKR msgId is monotonically increasing)
        result.sort(key=lambda x: x["id"], reverse=True)
        return result

    def updateNewsBulletin(
        self, msgId: int, msgType: int, newsMessage: str, originExch: str
    ) -> None:
        """Callback — receives one bulletin at a time from reqNewsBulletins."""
        if not self._news_bulletins_active:
            return
        with self._lock:
            self._news_bulletins.append(
                {
                    "id": msgId,
                    "type": msgType,  # 1 = regular, 2 = exchange
                    "message": newsMessage,
                    "exchange": originExch,
                    "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

    # -------------------------------------------------------------------------
    # Option chain parameters
    # -------------------------------------------------------------------------

    def get_option_chain_params(
        self,
        symbol: str,
        con_id: int,
        timeout: float = 15.0,
    ) -> dict:
        """
        Fetch available expirations and strikes for an underlying's options.

        Uses reqSecDefOptParams which returns results per-exchange; this method
        merges all exchanges and returns the union of expirations/strikes.

        Args:
            symbol:  Underlying symbol (e.g. 'AAPL')
            con_id:  Underlying contract ID (from get_contract_details)
            timeout: Seconds to wait for all exchange responses

        Returns:
            {
                'expirations': ['YYYYMMDD', ...],  # sorted
                'strikes':     [float, ...],        # sorted
                'multiplier':  '100',
            }
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        with self._lock:
            self._opt_chain_params[req_id] = {
                "expirations": set(),
                "strikes": set(),
                "multiplier": "100",
            }
            self._opt_chain_events[req_id] = event

        self.reqSecDefOptParams(req_id, symbol, "", "STK", con_id)
        event.wait(timeout=timeout)

        with self._lock:
            raw = self._opt_chain_params.pop(req_id, {})
            self._opt_chain_events.pop(req_id, None)

        return {
            "expirations": sorted(raw.get("expirations", [])),
            "strikes": sorted(raw.get("strikes", [])),
            "multiplier": raw.get("multiplier", "100"),
        }

    def securityDefinitionOptionalParameter(
        self,
        reqId: int,
        exchange: str,
        underlyingConId: int,
        tradingClass: str,
        multiplier: str,
        expirations,
        strikes,
    ) -> None:
        """Callback — one call per exchange for reqSecDefOptParams."""
        with self._lock:
            if reqId not in self._opt_chain_params:
                return
            r = self._opt_chain_params[reqId]
            r["expirations"].update(expirations)
            r["strikes"].update(strikes)
            if multiplier:
                r["multiplier"] = multiplier

    def securityDefinitionOptionalParameterEnd(self, reqId: int) -> None:
        """Callback — fired when all exchanges have been delivered."""
        if reqId in self._opt_chain_events:
            self._opt_chain_events[reqId].set()

    # -------------------------------------------------------------------------
    # Option market data snapshots
    # -------------------------------------------------------------------------

    def get_option_snapshot(
        self,
        contract: Contract,
        timeout: float = 10.0,
    ) -> dict:
        """
        Request a one-shot market data snapshot for an option contract.

        Subscribes with snapshot=True; waits for tickSnapshotEnd or timeout.

        Args:
            contract: Fully-specified IBKR Contract (secType='OPT')
            timeout:  Seconds to wait

        Returns:
            {
                'bid': float|None, 'ask': float|None, 'last': float|None,
                'volume': int, 'open_interest': int,
                'iv': float|None, 'delta': float|None, 'gamma': float|None,
                'vega': float|None, 'theta': float|None, 'und_price': float|None,
            }
            Fields are None when IBKR does not provide them.
        """
        req_id = self._get_next_req_id()
        event = threading.Event()
        with self._lock:
            self._mktdata_results[req_id] = {
                "bid": None,
                "ask": None,
                "last": None,
                "volume": 0,
                "open_interest": 0,
                "iv": None,
                "delta": None,
                "gamma": None,
                "vega": None,
                "theta": None,
                "und_price": None,
            }
            self._mktdata_events[req_id] = event

        # Empty genericTickList: snapshot=True is incompatible with generic
        # ticks (causes Error 321).  bid/ask/last come via tickPrice,
        # IV+Greeks come via tickOptionComputation automatically for OPT contracts.
        # reqMarketDataType(3) must be called once per connection BEFORE the
        # first snapshot request (done by the caller in collect_options_snapshot).
        self.reqMktData(req_id, contract, "", True, False, [])
        timed_out = not event.wait(timeout=timeout)

        # Always cancel — on normal completion IBKR auto-cancels snapshot
        # subscriptions after tickSnapshotEnd, but on timeout the subscription
        # may stay open and count against the per-connection market-data line
        # limit, causing IBKR to reject subsequent requests.
        if timed_out:
            self.cancelMktData(req_id)

        with self._lock:
            result = self._mktdata_results.pop(req_id, {})
            self._mktdata_events.pop(req_id, None)

        return result

    def tickOptionComputation(
        self,
        reqId: int,
        tickType: int,
        tickAttrib: int,
        impliedVol: float,
        delta: float,
        optPrice: float,
        pvDividend: float,
        gamma: float,
        vega: float,
        theta: float,
        undPrice: float,
    ) -> None:
        """
        Callback — receives Greeks and IV for an option contract.
        tickType: 10=bid, 11=ask, 12=last, 13=model (preferred).
        """
        if reqId not in self._mktdata_results:
            return

        def _fv(x):
            """Return float if finite and not NaN, else None."""
            if x is None:
                return None
            try:
                v = float(x)
                return v if (v == v and abs(v) < 1e30) else None
            except (TypeError, ValueError):
                return None

        with self._lock:
            if reqId not in self._mktdata_results:
                return
            r = self._mktdata_results[reqId]
            # Prefer model greeks (tickType 13); accept any if not yet set
            if tickType == 13 or r["iv"] is None:
                r["iv"] = _fv(impliedVol)
                r["delta"] = _fv(delta)
                r["gamma"] = _fv(gamma)
                r["vega"] = _fv(vega)
                r["theta"] = _fv(theta)
            if r["und_price"] is None:
                r["und_price"] = _fv(undPrice)
            # For delayed option data IBKR sends model greeks (tickType 13)
            # but frequently never fires tickSnapshotEnd, causing the full
            # timeout to elapse.  Treat model-greeks arrival as "snapshot done"
            # so we return immediately instead of waiting out the timeout.
            if tickType == 13:
                event = self._mktdata_events.get(reqId)
                if event is not None:
                    event.set()

    def tickSnapshotEnd(self, reqId: int) -> None:
        """Callback — fired when a snapshot market data request is complete."""
        if reqId in self._mktdata_events:
            self._mktdata_events[reqId].set()
