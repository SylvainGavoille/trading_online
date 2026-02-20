import logging
from typing import Dict, Any, Optional
from src.api.ib_connector import IBClient
from src.trading.agents.risk_validator import RiskValidator
from src.trading.agents.trade_executor import TradeExecutor
from src.trading.agents.signal_analyzer import SignalAnalyzer

class TradingLogic:
    """
    Core trading logic orchestrator that coordinates analysis, risk management,
    and trade execution using modular components.
    """
    
    def __init__(self, config: dict):
        """
        Initialize trading logic with configuration and dependencies
        
        Args:
            config: Trading configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.api_connector = IBClient(config)
        self.risk_validator = RiskValidator(config)
        self.trade_executor = TradeExecutor(self.api_connector)
        self.signal_analyzer = SignalAnalyzer(None)  # Technical analysis will be initialized with data later
        
        # Connect to trading platform
        if not self.api_connector.connect_and_run():
            self.logger.error("Failed to connect to trading platform")
    
    def execute_trade(self, symbol: str, order_type: str, quantity: int, 
                     price: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """
        Execute a trade with risk management and validation
        
        Args:
            symbol: The stock symbol to trade
            order_type: The type of order (market, limit, stop)
            quantity: The number of shares to trade
            price: The price for limit/stop orders (optional)
            
        Returns:
            Trade execution result or None if validation fails
        """
        try:
            self.logger.info(f"Executing trade for {symbol}")
            
            # Validate basic order parameters
            if not self._validate_order_params(quantity, order_type, price):
                return None
            
            # Get current market data
            self.logger.debug("Fetching market data")
            market_data = self.api_connector.get_market_data(symbol)
            if not market_data:
                self.logger.error("Failed to retrieve market data")
                return None
            
            # Calculate trade parameters using signal analyzer
            self.logger.debug("Analyzing market data")
            analysis = self.signal_analyzer.analyze_market_data(symbol, market_data)
            if analysis['status'] != 'success':
                self.logger.error(f"Market data analysis failed: {analysis['reason']}")
                return None
            
            # Prepare trade parameters
            trade_params = self._calculate_trade_parameters(
                symbol, order_type, quantity, price,
                analysis['technical_indicators']
            )
            
            # Validate against risk management rules
            self.logger.info("Validating trade parameters")
            portfolio = self.trade_executor.get_portfolio()
            risk_result = self.risk_validator.validate_trade(trade_params, portfolio)
            
            if not risk_result['approved']:
                self.logger.warning(f"Trade rejected by risk management: {risk_result['reason']}")
                return None
            
            # Execute the trade
            self.logger.info("Executing trade")
            execution_result = self.trade_executor.execute_trade(trade_params)
            
            if execution_result['status'] == 'executed':
                self.logger.info(f"Trade executed successfully: {execution_result}")
                return execution_result
            else:
                self.logger.error(f"Trade execution failed: {execution_result['reason']}")
                return None
                
        except Exception as e:
            self.logger.exception(f"Error executing trade: {str(e)}")
            return None
    
    def evaluate_trading_opportunity(self, symbol: str, 
                                  market_data: Dict[str, Any]) -> Optional[float]:
        """
        Evaluate trading opportunity using signal analyzer
        
        Args:
            symbol: The stock symbol to evaluate
            market_data: Market data for analysis
            
        Returns:
            Signal score or None if evaluation fails
        """
        try:
            self.logger.info(f"Evaluating trading opportunity for {symbol}")
            
            if not market_data or not isinstance(market_data, dict):
                self.logger.error("Invalid market data format")
                return None
            
            # Analyze market data
            analysis = self.signal_analyzer.analyze_market_data(symbol, market_data)
            if analysis['status'] != 'success':
                self.logger.error(f"Market data analysis failed: {analysis['reason']}")
                return None
            
            # Extract technical signal
            technical_indicators = analysis['technical_indicators']
            if technical_indicators:
                signal = (technical_indicators['price_target'] - technical_indicators['current_price']) / technical_indicators['current_price']
                normalized_signal = max(min(signal / 0.02, 1.0), -1.0)  # Normalize to [-1, 1] range with 2% as reference
                self.logger.info(f"Calculated signal: {normalized_signal}")
                return normalized_signal
            
            return None
            
        except Exception as e:
            self.logger.exception(f"Error evaluating trading opportunity: {str(e)}")
            return None
    
    def _validate_order_params(self, quantity: int, order_type: str, 
                             price: Optional[float]) -> bool:
        """Validate basic order parameters"""
        try:
            if quantity <= 0:
                self.logger.error("Invalid quantity: must be greater than zero")
                return False
                
            if order_type not in ["market", "limit", "stop"]:
                self.logger.error(f"Invalid order type: {order_type}")
                return False
                
            if order_type in ["limit", "stop"] and price is None:
                self.logger.error("Price must be specified for limit/stop orders")
                return False
                
            return True
            
        except Exception as e:
            self.logger.exception(f"Error validating order parameters: {str(e)}")
            return False
    
    def _calculate_trade_parameters(self, symbol: str, order_type: str,
                                 quantity: int, price: Optional[float],
                                 indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate complete trade parameters including risk levels"""
        try:
            current_price = price or indicators['current_price']
            
            return {
                "symbol": symbol,
                "order_type": order_type,
                "size": quantity,
                "price": current_price,
                "stop_loss": indicators['stop_loss'],
                "target_price": indicators['price_target'],
                "atr": indicators['atr']
            }
            
        except Exception as e:
            self.logger.exception(f"Error calculating trade parameters: {str(e)}")
            raise
