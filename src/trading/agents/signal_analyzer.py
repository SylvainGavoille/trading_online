import logging
from typing import Dict, Any, Optional
import pandas as pd
import json
from datetime import datetime, UTC
from src.analysis.technical_analysis import TechnicalAnalysis

class SignalAnalyzer:
    """Handles analysis of technical and sentiment signals"""
    
    def __init__(self, technical_analysis: TechnicalAnalysis):
        """
        Initialize signal analyzer
        
        Args:
            technical_analysis: Technical analysis component
        """
        self.technical_analysis = technical_analysis
        self.logger = logging.getLogger(__name__)
    
    def analyze_market_data(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market data using technical and sentiment indicators
        
        Args:
            symbol: Trading symbol
            market_data: Market data dictionary or DataFrame
            
        Returns:
            Analysis results including signals and calculations
        """
        self.logger.info(f"Analyzing market data for {symbol}")
        
        # Convert market data to proper format
        df = self._prepare_market_data(market_data)
        if df is None:
            self.logger.error("Failed to prepare market data")
            return {"status": "error", "reason": "Invalid market data format"}
            
        try:
            # Update technical analysis with current data
            self.technical_analysis.data = df
            
            # Get current price and calculate indicators
            current_price = float(df['close'].iloc[-1])
            self.logger.debug(f"Current price: {current_price}")
            
            # Calculate technical indicators
            atr = self.technical_analysis.calculate_atr(symbol) or (current_price * 0.01)
            price_target = self.technical_analysis.calculate_price_target(symbol) or (current_price * 1.02)
            
            # Calculate stop loss
            stop_loss = current_price - (atr * 2)  # Using 2x ATR for stop loss
            
            self.logger.debug(f"Calculated indicators - ATR: {atr}, Target: {price_target}, Stop: {stop_loss}")
            
            # Get sentiment analysis
            sentiment_scores = self._analyze_sentiment(symbol)
            self.logger.debug(f"Sentiment scores: {sentiment_scores}")
            
            return {
                "status": "success",
                "technical_indicators": {
                    "current_price": current_price,
                    "atr": atr,
                    "price_target": price_target,
                    "stop_loss": stop_loss
                },
                "sentiment": sentiment_scores
            }
            
        except Exception as e:
            self.logger.exception(f"Error analyzing market data: {str(e)}")
            return {"status": "error", "reason": str(e)}
    
    def _prepare_market_data(self, market_data: Any) -> Optional[pd.DataFrame]:
        """Convert market data to DataFrame format"""
        try:
            if isinstance(market_data, pd.DataFrame):
                return market_data
                
            if isinstance(market_data, dict):
                data_dict = {
                    "close": market_data["close"],
                    "high": market_data.get("high", []),
                    "low": market_data.get("low", []),
                    "volume": market_data.get("volume", []),
                    "timestamp": market_data.get("timestamp", [
                        datetime.now(UTC).isoformat()
                    ])
                }
                return pd.DataFrame(data_dict)
                
            return None
            
        except Exception as e:
            self.logger.exception(f"Error preparing market data: {str(e)}")
            return None
    
    def _analyze_sentiment(self, symbol: str) -> Dict[str, float]:
        """
        Analyze market sentiment from various sources
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Dictionary containing sentiment scores
        """
        try:
            # Get news sentiment
            news_score = self._fetch_news_sentiment(symbol)
            self.logger.debug(f"News sentiment score: {news_score}")
            
            # Get social sentiment
            social_score = self._fetch_social_sentiment(symbol)
            self.logger.debug(f"Social sentiment score: {social_score}")
            
            # Calculate aggregate sentiment
            aggregate_score = self._calculate_aggregate_sentiment(news_score, social_score)
            self.logger.debug(f"Aggregate sentiment score: {aggregate_score}")
            
            return {
                "news": news_score,
                "social": social_score,
                "aggregate": aggregate_score
            }
            
        except Exception as e:
            self.logger.exception(f"Error analyzing sentiment: {str(e)}")
            return {
                "news": 0.5,
                "social": 0.5,
                "aggregate": 0.5
            }
    
    def _fetch_news_sentiment(self, symbol: str) -> float:
        """
        Fetch and analyze news sentiment
        
        Currently returns neutral sentiment (0.5) as a baseline.
        This should be replaced with actual news sentiment analysis implementation.
        """
        self.logger.info(f"Fetching news sentiment for {symbol}")
        return 0.5
    
    def _fetch_social_sentiment(self, symbol: str) -> float:
        """
        Fetch and analyze social media sentiment
        
        Currently returns neutral sentiment (0.5) as a baseline.
        This should be replaced with actual social sentiment analysis implementation.
        """
        self.logger.info(f"Fetching social sentiment for {symbol}")
        return 0.5
    
    def _calculate_aggregate_sentiment(self, news_score: float, social_score: float) -> float:
        """
        Calculate aggregate sentiment from individual scores
        
        Args:
            news_score: News sentiment score
            social_score: Social sentiment score
            
        Returns:
            Aggregate sentiment score
        """
        # Simple weighted average: 60% news, 40% social
        return (news_score * 0.6) + (social_score * 0.4)
    
    def calculate_position_size(self, config: dict, portfolio_value: float, 
                              current_price: float, stop_loss: float) -> int:
        """
        Calculate appropriate position size based on risk parameters
        
        Args:
            config: Trading configuration
            portfolio_value: Current portfolio value
            current_price: Current asset price
            stop_loss: Stop loss price level
            
        Returns:
            Position size in number of units
        """
        try:
            self.logger.info("Calculating position size")
            
            # Get risk per trade from config
            risk_per_trade = config['execution']['position_sizing']['risk_per_trade']
            max_position_size = config['risk_management']['position_limits']['max_position_size']
            
            # Calculate risk amount
            risk_amount = portfolio_value * risk_per_trade
            
            # Calculate price risk
            price_risk = current_price - stop_loss
            
            # Calculate position size based on risk
            if price_risk <= 0:
                self.logger.warning("Invalid price risk (zero or negative)")
                return 0
                
            position_size = min(
                int(risk_amount / price_risk),
                max_position_size
            )
            
            self.logger.debug(f"Calculated position size: {position_size}")
            return max(0, position_size)
            
        except Exception as e:
            self.logger.exception(f"Error calculating position size: {str(e)}")
            return 0
