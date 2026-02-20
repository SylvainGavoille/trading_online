import unittest
from unittest.mock import patch, MagicMock
from src.trading.agents.agent_manager import AgentManager

class TestAgentManager(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'api': {
                'tws_endpoint': 'localhost',
                'port': 7496
            }
        }
        # Patch the Swarm class to mock its behavior
        with patch('src.trading.agents.agent_manager.Swarm') as mock_swarm:
            self.mock_swarm = mock_swarm.return_value
            self.agent_manager = AgentManager(self.config)

    def test_agent_initialization(self):
        """Test agent initialization and structure"""
        # Verify all required agents are created
        required_agents = ['technical', 'sentiment', 'risk', 'execution']
        for agent_type in required_agents:
            self.assertIn(agent_type, self.agent_manager.agents)
            # Check agent structure
            agent = self.agent_manager.agents[agent_type]
            self.assertIsNotNone(agent.name)
            self.assertIsNotNone(agent.instructions)

    def test_get_agent(self):
        """Test agent retrieval"""
        # Test valid agent retrieval
        agent = self.agent_manager.get_agent('technical')
        self.assertIsNotNone(agent)
        
        # Test invalid agent type
        agent = self.agent_manager.get_agent('invalid')
        self.assertIsNone(agent)

    def test_run_agent_success(self):
        """Test successful agent execution"""
        # Setup mock response
        expected_response = {
            "messages": [
                {"content": '{"signal": "buy", "confidence": 0.8}'}
            ]
        }
        self.mock_swarm.run.return_value = MagicMock(**expected_response)
        
        # Run agent
        messages = [{'role': 'user', 'content': 'Analyze market data'}]
        response = self.agent_manager.run_agent('technical', messages)
        
        # Verify response and interaction
        self.assertIsNotNone(response)
        self.assertEqual(response.messages[0]['content'], expected_response["messages"][0]["content"])
        self.mock_swarm.run.assert_called_once_with(agent=self.agent_manager.agents['technical'], messages=messages)

    def test_run_agent_error_handling(self):
        """Test agent execution error handling"""
        # Test with invalid agent type
        messages = [{'role': 'user', 'content': 'Analyze market data'}]
        response = self.agent_manager.run_agent('invalid', messages)
        self.assertIsNone(response)
        self.mock_swarm.run.assert_not_called()
        
        # Test with execution error
        self.mock_swarm.run.side_effect = Exception('Agent error')
        response = self.agent_manager.run_agent('technical', messages)
        self.assertIsNone(response)
        self.mock_swarm.run.assert_called_once_with(agent=self.agent_manager.agents['technical'], messages=messages)

if __name__ == '__main__':
    unittest.main()