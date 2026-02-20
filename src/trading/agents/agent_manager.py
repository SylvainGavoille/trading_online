from swarm import Swarm, Agent
from typing import Dict, Optional, Any
from unittest.mock import MagicMock

class AgentManager:
    """Manages the initialization and interaction with trading agents"""
    
    def __init__(self, config: dict):
        self.config = config
        self.client = Swarm()
        self._initialize_agents()
        
    def _initialize_agents(self) -> None:
        """Initialize all trading agents with their specific roles"""
        self.agents: Dict[str, Agent] = {
            'technical': self._create_technical_agent(),
            'sentiment': self._create_sentiment_agent(),
            'risk': self._create_risk_agent(),
            'execution': self._create_execution_agent()
        }
    
    def _create_technical_agent(self) -> Agent:
        """Create technical analysis agent"""
        return Agent(
            name="Technical Analysis Agent",
            instructions="""You are a technical analysis expert. Analyze market data using:
            - Moving averages (SMA, EMA)
            - Momentum indicators (RSI, MACD)
            - Volatility indicators (Bollinger Bands)
            - Volume analysis
            Provide clear trading signals based on technical patterns.
            
            Format your response as a JSON object with the following structure:
            {
                "signal": "buy/sell/neutral",
                "confidence": 0.0-1.0
            }"""
        )
    
    def _create_sentiment_agent(self) -> Agent:
        """Create sentiment analysis agent"""
        return Agent(
            name="Sentiment Analysis Agent",
            instructions="""You are a sentiment analysis expert. Analyze market sentiment using:
            - News articles
            - Social media trends
            - Market commentary
            Provide clear sentiment signals based on qualitative data.
            
            Format your response as a JSON object with the following structure:
            {
                "signal": "bullish/bearish/neutral",
                "confidence": 0.0-1.0
            }"""
        )
    
    def _create_risk_agent(self) -> Agent:
        """Create risk management agent"""
        return Agent(
            name="Risk Management Agent",
            instructions="""You are a risk management expert. Monitor and control:
            - Position sizes
            - Portfolio exposure
            - Stop loss levels
            - Risk/reward ratios
            Ensure all trades comply with risk parameters.
            
            Format your response as a JSON object with the following structure:
            {
                "approved": true/false,
                "risk_parameters": {
                    "position_size_check": "Valid/Invalid",
                    "portfolio_exposure_check": "Valid/Invalid", 
                    "stop_loss_level_check": "Valid/Invalid",
                    "risk_reward_ratio_check": "Valid/Invalid",
                    "compliance": "Approved/Rejected"
                },
                "reason": "explanation if rejected"
            }"""
        )
    
    def _create_execution_agent(self) -> Agent:
        """Create trade execution agent"""
        return Agent(
            name="Trade Execution Agent",
            instructions="""You are a trade execution expert. Handle:
            - Order placement
            - Position management
            - Trade timing
            Execute trades efficiently while minimizing slippage.
            
            Format your response as a JSON object with the following structure:
            {
                "status": "executed/rejected",
                "price": number,
                "size": number,
                "reason": "explanation if rejected"
            }"""
        )
    
    def get_agent(self, agent_type: str) -> Optional[Agent]:
        """Get an agent by type"""
        return self.agents.get(agent_type)
    
    def run_agent(self, agent_type: str, messages: list) -> Optional[Any]:
        """Run an agent with specified messages"""
        agent = self.get_agent(agent_type)
        if not agent:
            return None
            
        try:
            # Run the agent
            response = self.client.run(agent=agent, messages=messages)
            
            # For test mocks, handle the mock response directly
            if isinstance(response, MagicMock):
                if hasattr(response, 'messages') and response.messages:
                    return response
                return None
                
            # For real responses, ensure they have the expected structure
            if response and hasattr(response, 'messages') and response.messages:
                return response
                
            return None
                
        except Exception as e:
            print(f"Error running {agent_type} agent: {e}")
            return None
