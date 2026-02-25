# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Quantum Trader** is an algorithmic trading system using a **DSPy multi-agent architecture** for autonomous market analysis, risk management, and trade execution via Interactive Brokers. The system has two main interfaces: a **CLI trading bot** (`run_trader.py`) and a **Streamlit dashboard** (`dashboard/dashboard_app.py`) for portfolio management and market analysis.

## Commands

### Setup and Dependencies

```bash
# Install all dependencies
uv sync

# Verify IBKR connection
uv run python test_connection.py

# Full diagnostic
uv run python diagnose_connection.py
```

### Running the Trading Bot

```bash
# Paper trading with Ollama (default, free)
uv run python run_trader.py --symbols AAPL MSFT --mode paper

# With specific LLM provider
uv run python run_trader.py --symbols AAPL --llm openai --model gpt-4o-mini --mode paper
uv run python run_trader.py --symbols AAPL --llm anthropic --model claude-3-5-sonnet-20241022 --mode paper
```

### Running the Dashboard

```bash
# Using convenience scripts
./run_dashboard.sh      # Linux/macOS
run_dashboard.bat       # Windows

# Direct launch
cd dashboard
uv run streamlit run dashboard_app.py
```

### Testing

```bash
# Run all tests
uv run python -m unittest discover tests

# Test specific components
cd dashboard
uv run python test_dashboard.py          # Dashboard integration
uv run python test_ibkr_portfolio.py     # IBKR portfolio integration
uv run python test_integration.py        # Portfolio + risk profile
```

### Training System

```bash
cd training
python server.py
# Open http://localhost:7555 in browser
```

## Architecture

### Multi-Agent DSPy System

The core trading logic uses **4 specialized DSPy agents** that communicate and collaborate:

1. **Technical Analysis Agent** (`src/agents/technical_agent.py`)
   - Calculates indicators: SMA, EMA, RSI, MACD, Bollinger Bands
   - Outputs: BUY/SELL/HOLD with confidence score

2. **Sentiment Analysis Agent** (`src/agents/sentiment_agent.py`)
   - Analyzes news and social media
   - Outputs: BULLISH/BEARISH/NEUTRAL with confidence

3. **Risk Management Agent** (`src/agents/risk_agent.py`)
   - Validates position sizes, stop-loss levels, risk/reward ratios
   - Outputs: APPROVE/REJECT with risk metrics

4. **Execution Agent** (`src/agents/execution_agent.py`)
   - Places orders via IBKR API
   - Manages slippage, order types (market/limit)

**Key Pattern**: Agents are chained via DSPy's `ChainOfThought` pattern. The orchestrator (`src/trading/orchestrator.py`) coordinates the flow:

```
Market Data → Technical Agent → Sentiment Agent → Risk Agent → Execution Agent → IBKR
```

### IBKR Integration

**Connection Layer** (`src/api/ib_connector.py`):

- `IBClient` class wraps `ibapi.EClient` and `ibapi.EWrapper`
- Implements threaded message loop for async callbacks
- Provides methods:
  - `get_account_positions()` - Real positions from account
  - `get_account_summary()` - Cash balance, buying power
  - `get_market_data(symbol)` - Current prices (delayed or real-time)
  - `get_historical_data(symbol, period, interval)` - OHLCV bars
  - `search_contracts(pattern)` - Search for instruments
  - `get_contract_details(symbol)` - Full contract info

**Global Client Pattern**: The dashboard and other components share a single IBKR connection via dependency injection:

```python
# Dashboard initialization
ib_client = get_ib_client()  # Cached resource
configure_ibkr_client(ib_client)  # Inject into managers

# Portfolio manager uses global client
_ib_client = None  # Module-level
def configure_ibkr_client(client):
    global _ib_client
    _ib_client = client
```

### Dashboard Architecture

**Entry Point**: `dashboard/dashboard_app.py`

**4 Main Tabs**:

1. **🔍 Exploration** - Search stocks, view charts, LLM analysis
2. **📊 Portfolio** - Real-time positions from IBKR or local JSON
3. **⚙️ Configuration** - Risk profile management
4. **📚 Documentation** - Guides

**Data Sources**:

- **IBKR Connected**: Positions, prices, cash from live account
- **Offline Mode**: Falls back to `portfolio.json`, `user_config.json`, Yahoo Finance prices

**Key Managers**:

- `PortfolioManager` (`dashboard/portfolio_manager.py`)
  - Loads positions from IBKR via `_load_from_ibkr()`
  - Calculates fees based on IBKR plan (Lite/Pro Fixed/Pro Tiered)
  - Computes real vs IBKR-displayed gains (with/without fees)

- `RiskProfileManager` (`dashboard/risk_profile_manager.py`)
  - 4 profiles: Conservateur, Modéré, Agressif, Très Agressif
  - Validates position sizes against profile limits
  - Stores config in `user_config.json`

**Stock Search**: Uses `src/agents/stock_search_agent.py` with DSPy for intelligent filtering. Fallback to `simple_stock_search()` without LLM. Search is powered by `src/data/dynamic_stocks.py` using Yahoo Finance API (`yf.Search()`).

## Configuration

**Main Config**: `src/config/config.yaml`

Key sections:

- `api.port`: 7497 (TWS paper), 4002 (IB Gateway paper), 7496 (TWS live), 4001 (Gateway live)
- `technical_analysis.indicators`: Periods for SMA, EMA, RSI, MACD, Bollinger
- `risk_management`: Position limits, stop-loss, daily loss limit, max drawdown
- `execution`: Order types, slippage tolerance, position sizing method
- `multi_agent`: LLM provider/model config (ollama/openai/anthropic)
- `fees.ibkr_plan`: "lite" | "pro_fixed" | "pro_tiered"

**Dashboard Config**: `dashboard/user_config.json` (auto-created)

```json
{
  "risk_profile": "Modéré",
  "capital_initial": 10000.0,
  "available_cash": 10000.0,
  "max_loss_per_trade": 2.0,
  "max_portfolio_risk": 10.0,
  "ibkr_plan": "Lite"
}
```

## LLM Provider Configuration

**Default**: Ollama + DeepSeek-R1 (local, free)

**Setup**:

```bash
# Install Ollama from https://ollama.ai
ollama pull deepseek-r1:14b

# Configure in src/config/config.yaml
multi_agent:
  llm_provider: ollama  # or openai, anthropic
  model_name: deepseek-r1:14b
```

**Alternative Providers**:

- OpenAI: Set `OPENAI_API_KEY` env var
- Anthropic: Set `ANTHROPIC_API_KEY` env var

DSPy automatically configures the LM based on provider:

```python
if provider == 'openai':
    lm = dspy.LM(model=f'openai/{model}', api_key=os.getenv('OPENAI_API_KEY'))
elif provider == 'anthropic':
    lm = dspy.LM(model=f'anthropic/{model}', api_key=os.getenv('ANTHROPIC_API_KEY'))
else:
    lm = dspy.LM(model=f'ollama/{model}', api_base='http://localhost:11434')
dspy.configure(lm=lm)
```

## Important Patterns

### DSPy Agent Pattern

```python
class StockAnalysis(dspy.Signature):
    """Signature defining inputs/outputs"""
    market_data: str = dspy.InputField(desc="Current market data")
    analysis: str = dspy.OutputField(desc="Trading recommendation")

# Create agent with ChainOfThought
analyze_stock = dspy.ChainOfThought(StockAnalysis)

# Use agent (NOT .forward())
result = analyze_stock(market_data=data)  # Direct call
```

**Critical**: Call agents directly `agent(...)`, not `agent.forward(...)` - DSPy deprecated the latter.

### IBKR Callback Pattern

All IBKR API methods are async callbacks:

```python
def position(self, account: str, contract, position: float, avgCost: float):
    """Callback receives positions"""
    self._positions[contract.symbol] = {
        'position': position,
        'avg_cost': avgCost
    }

def positionEnd(self):
    """Callback signals completion"""
    self._positions_event.set()  # Unblock waiting thread
```

Use threading events to synchronize:

```python
event = threading.Event()
self.reqPositions()  # Async request
event.wait(timeout=10.0)  # Block until positionEnd() sets event
```

### Streamlit Caching

Use `@st.cache_resource` for expensive initialization:

```python
@st.cache_resource
def get_ib_client() -> Optional[IBClient]:
    """Single shared IBKR connection"""
    client = IBClient(config)
    if client.connect_and_run():
        return client
    return None
```

### Dual-Mode Portfolio

`PortfolioManager` operates in two modes:

**Mode 1: IBKR Connected**

```python
pm = PortfolioManager(use_ibkr=True)
positions = pm._load_from_ibkr()  # Via IBClient API
prices = _ib_client.get_market_data(symbol)
cash = pm.get_account_cash_from_ibkr()  # TotalCashValue
```

**Mode 2: Offline**

```python
positions = json.load(open('portfolio.json'))  # Manual entries
prices = yf.Ticker(symbol).history(period="1d")  # Yahoo Finance
cash = risk_manager.get_available_cash()  # From config
```

## Key Files

### Core Trading

- `run_trader.py` - Main entry point for trading bot
- `src/trading/orchestrator.py` - Coordinates all agents
- `src/api/ib_connector.py` - IBKR API wrapper with all methods
- `src/config/config.yaml` - System configuration

### Agents (DSPy)

- `src/agents/technical_agent.py` - Technical analysis
- `src/agents/sentiment_agent.py` - Sentiment analysis
- `src/agents/risk_agent.py` - Risk validation
- `src/agents/execution_agent.py` - Order execution
- `src/agents/stock_search_agent.py` - Dashboard stock search

### Dashboard

- `dashboard/dashboard_app.py` - Streamlit main app (900+ lines)
- `dashboard/portfolio_manager.py` - Portfolio with IBKR integration
- `dashboard/risk_profile_manager.py` - Risk profile logic
- `src/data/dynamic_stocks.py` - Stock search via Yahoo Finance API

### Analysis

- `src/analysis/technical_analysis.py` - Indicator calculations
- `src/analysis/qualitative_analysis.py` - Sentiment analysis

## Testing Strategy

- **Unit tests**: `tests/` directory - individual components
- **Integration tests**: `dashboard/test_*.py` - end-to-end flows
- **Connection tests**: `test_connection.py`, `diagnose_connection.py`

When adding features:

1. Add unit test in `tests/`
2. Add integration test in `dashboard/test_*.py` if UI-related
3. Update relevant documentation in `dashboard/docs/`

## Common Modifications

### Adding a new technical indicator

1. Add calculation to `src/analysis/technical_analysis.py`
2. Add config to `src/config/config.yaml` under `technical_analysis.indicators`
3. Update `src/agents/technical_agent.py` to use indicator
4. Update `docs/INDICATORS.md` documentation

### Adding a new risk profile

1. Add profile to `RISK_PROFILES` dict in `dashboard/risk_profile_manager.py`
2. Define allocation, instruments, max_position_size, etc.
3. Update `dashboard/docs/PORTFOLIO_AND_CONFIG.md`

### Changing IBKR fee structure

1. Modify `IBKR_FEES` dict in `dashboard/portfolio_manager.py`
2. Update `calculate_fees()` method
3. Test with `dashboard/test_integration.py`

## Documentation

**Quick references** in `dashboard/docs/`:

- `IBKR_INTEGRATION.md` - IBKR API usage, connection, callbacks
- `PORTFOLIO_AND_CONFIG.md` - Portfolio tab usage, risk profiles
- `LLM_CONFIGURATION.md` - LLM provider setup (Ollama/OpenAI/Anthropic)
- `DYNAMIC_SEARCH_SYSTEM.md` - Stock search implementation

**Full guides** in `docs/`:

- `docs/ARCHITECTURE.md` - System architecture
- `docs/AGENTS_SYSTEM.md` - Multi-agent design
- `docs/WORKFLOW.md` - Trading decision flow
- `docs/RISK_MANAGEMENT_DETAILED.md` - Risk calculation details

## Prerequisites for Development

1. **TWS or IB Gateway** running (for IBKR features)
   - Paper trading: Port 7497 (TWS) or 4002 (Gateway)
   - Live trading: Port 7496 (TWS) or 4001 (Gateway)
   - Enable API in: File → Global Configuration → API → Settings

2. **Ollama** installed (for free LLM)

   ```bash
   # Download from https://ollama.ai
   ollama pull deepseek-r1:14b
   ```

3. **Python 3.12+** with `uv` package manager

## Security Notes

- **Read-Only API**: Enable in TWS for safety (dashboard only reads data)
- **Paper Trading**: Always test with `--mode paper` first
- **Credentials**: Never commit API keys - use environment variables
- **Risk Limits**: Configure in `config.yaml` before live trading

## Documentation

Stop documenting any modifications done
