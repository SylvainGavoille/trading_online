import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np
from datetime import datetime
import json
from swarm import Swarm, Agent

class TradingSwarm:
    """
    Coordinates multiple trading agents to analyze market opportunities and execute trades
    """
    
    def __init__(self, config: dict):
        """
        Initialize trading swarm with configuration
        
        Args:
            config: Trading configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = Swarm()
        
        # Initialize agents
        self.technical_agent = self._initialize_agent("technical")
        self.sentiment_agent = self._initialize_agent("sentiment")
        self.risk_agent = self._initialize_agent("risk")
        self.execution_agent = self._initialize_agent("execution")
        
    def _initialize_agent(self, agent_type: str) -> Agent:
        """Initialize a specific type of agent"""
        agent_configs = {
            'technical': Agent(
                name="Technical Analysis Agent",
                instructions="""You are a technical analysis expert. Analyze market data using:
                - Moving averages (SMA, EMA)
                - Momentum indicators (RSI, MACD)
                - Volatility indicators (Bollinger Bands)
                - Volume analysis
                Provide clear trading signals based on technical patterns."""
            ),
            'sentiment': Agent(
                name="Sentiment Analysis Agent",
                instructions="""You are a sentiment analysis expert. Analyze market sentiment using:
                - News articles
                - Social media trends
                - Market commentary
                Provide clear sentiment signals based on qualitative data."""
            ),
            'risk': Agent(
                name="Risk Management Agent",
                instructions="""You are a risk management expert. Monitor and control:
                - Position sizes
                - Portfolio exposure
                - Stop loss levels
                - Risk/reward ratios
                Ensure all trades comply with risk parameters."""
            ),
            'execution': Agent(
                name="Trade Execution Agent",
                instructions="""You are a trade execution expert. Handle:
                - Order placement
                - Position management
                - Trade timing
                Execute trades efficiently while minimizing slippage."""
            )
        }
        
        return agent_configs[agent_type]

    def _calculate_rsi(self, data) -> Optional[float]:
        """
        Calculate RSI (Relative Strength Index)
        
        Args:
            data: DataFrame or dict with price data
            
        Returns:
            RSI value or None if calculation fails
        """
        try:
            # Convert dict to DataFrame if needed
            if isinstance(data, dict):
                if not data.get('close'):
                    return None
                df = pd.DataFrame(data)
            elif isinstance(data, pd.DataFrame):
                if 'close' not in data.columns:
                    return None
                df = data
            else:
                return None
            
            # Need at least 3 data points for meaningful RSI
            if len(df) < 3:
                return None
                
            # Calculate price changes
            delta = df['close'].diff()
            
            # Handle constant prices
            if (delta == 0).all():
                return 50.0  # Neutral RSI for constant prices
            
            # Separate gains and losses
            gains = delta.copy()
            losses = delta.copy()
            gains[gains < 0] = 0
            losses[losses > 0] = 0
            losses = abs(losses)
            
            # Calculate average gains and losses
            avg_gain = gains.mean()
            avg_loss = losses.mean()
            
            if avg_loss == 0:
                if avg_gain == 0:
                    return 50.0  # Neutral RSI when no price changes
                return 100.0  # All gains
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return float(rsi)
            
        except Exception as e:
            self.logger.error(f"Error calculating RSI: {str(e)}")
            return None

    def _fetch_news_sentiment(self, symbol: str) -> float:
        """Fetch and analyze news sentiment"""
        # Default implementation returns neutral sentiment
        return 0.5

    def _fetch_social_sentiment(self, symbol: str) -> float:
        """Fetch and analyze social media sentiment"""
        # Default implementation returns neutral sentiment
        return 0.5

    def _aggregate_sentiment(self) -> float:
        """Aggregate different sentiment sources"""
        # Default implementation returns neutral sentiment
        return 0.5

    def _parse_agent_response(self, response) -> dict:
        """
        Parse agent response into a structured format
        
        Args:
            response: Agent response object
            
        Returns:
            Parsed response as dictionary
        """
        if not response or not hasattr(response, 'messages') or not response.messages:
            return {}
            
        content = response.messages[0].get('content')
        if not content:
            return {}
            
        # If content is already a dict, return it
        if isinstance(content, dict):
            return content
            
        try:
            # Try to parse as JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, return as processed message
            return {
                "status": "processed",
                "message": content
            }

    def _check_risk_approval(self, risk_response: dict) -> bool:
        """
        Check if trade is approved by risk management
        
        Args:
            risk_response: Risk analysis response
            
        Returns:
            True if trade is approved, False otherwise
        """
        if not isinstance(risk_response, dict):
            return False
            
        # Handle nested content structure
        if 'content' in risk_response:
            risk_response = risk_response['content']
            
        # Check approval status
        if not risk_response.get('approved', False):
            return False
            
        # Validate risk parameters
        risk_params = risk_response.get('risk_parameters', {})
        required_checks = [
            'position_size_check',
            'portfolio_exposure_check',
            'stop_loss_level_check',
            'risk_reward_ratio_check'
        ]
        
        return all(risk_params.get(check) == 'Valid' for check in required_checks)

    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit has been reached"""
        # Default implementation always returns True
        return True

    def analyze_trading_opportunity(self, symbol: str, market_data: Any) -> Dict[str, Any]:
        """
        Analyze trading opportunity using all agents
        
        Args:
            symbol: Trading symbol
            market_data: Market data for analysis
            
        Returns:
            Analysis results including execution status
        """
        try:
            # Validate market data
            if not isinstance(market_data, (pd.DataFrame, dict)):
                return {
                    "status": "error",
                    "reason": f"Invalid market data type: {type(market_data).__name__}"
                }
                
            if isinstance(market_data, dict) and not market_data.get('close'):
                return {
                    "status": "error",
                    "reason": "No price data available"
                }
                
            # Get technical analysis
            technical_message = [{
                "role": "user",
                "content": f"Analyze technical indicators for {symbol}"
            }]
            technical_response = self.client.run(agent=self.technical_agent, messages=technical_message)
            technical_data = self._parse_agent_response(technical_response)
            
            if "error" in technical_data:
                return {
                    "status": "error",
                    "reason": f"Technical analysis error: {technical_data['error']}"
                }
                
            # Get sentiment analysis
            sentiment_message = [{
                "role": "user",
                "content": f"Analyze market sentiment for {symbol}"
            }]
            sentiment_response = self.client.run(agent=self.sentiment_agent, messages=sentiment_message)
            sentiment_data = self._parse_agent_response(sentiment_response)
            
            # Prepare trade parameters
            trade_params = {
                "symbol": symbol,
                "price": market_data['close'][-1] if isinstance(market_data, dict) else market_data['close'].iloc[-1],
                "timestamp": datetime.now().strftime("%Y-%m-%d")
            }
            
            # Get risk analysis
            risk_message = [{
                "role": "user",
                "content": {
                    "symbol": symbol,
                    "trade": trade_params,
                    "technical": technical_data,
                    "sentiment": sentiment_data
                }
            }]
            risk_response = self.client.run(agent=self.risk_agent, messages=risk_message)
            risk_data = self._parse_agent_response(risk_response)
            
            # Check risk approval
            if not self._check_risk_approval(risk_data):
                return {
                    "status": "rejected",
                    "reason": risk_data.get('reason', 'Risk checks failed'),
                    "risk_parameters": risk_data.get('risk_parameters', {})
                }
                
            # Execute trade if approved
            execution_message = [{
                "role": "user",
                "content": {
                    "action": "execute",
                    "trade": trade_params
                }
            }]
            execution_response = self.client.run(agent=self.execution_agent, messages=execution_message)
            execution_data = self._parse_agent_response(execution_response)
            
            return execution_data
            
        except Exception as e:
            self.logger.exception(f"Error analyzing trading opportunity: {str(e)}")
            return {
                "status": "error",
                "reason": str(e)
            }
