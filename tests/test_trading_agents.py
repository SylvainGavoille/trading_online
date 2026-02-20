import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from datetime import datetime
from src.trading.trading_agents import TradingSwarm

class TestTradingSwarm(unittest.TestCase):
    def setUp(self):
        """Initialize test environment"""
        self.config = {
            "risk_management": {
                "position_limits": {
                    "max_position_size": 100
                },
                "loss_limits": {
                    "daily_loss_limit": 1000
                }
            }
        }
        
        # Sample market data for testing
        self.market_data_df = pd.DataFrame({
            'close': [100.0, 101.0, 102.0, 101.5, 103.0],
            'high': [101.0, 102.0, 103.0, 102.5, 104.0],
            'low': [99.0, 100.0, 101.0, 100.5, 102.0],
            'volume': [1000, 1100, 1200, 1150, 1300]
        }, index=pd.date_range(start='2024-01-01', periods=5))
        
        self.market_data_dict = {
            'close': [100.0, 101.0, 102.0, 101.5, 103.0],
            'high': [101.0, 102.0, 103.0, 102.5, 104.0],
            'low': [99.0, 100.0, 101.0, 100.5, 102.0],
            'volume': [1000, 1100, 1200, 1150, 1300],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05']
        }

        # Create a mock Swarm instance
        self.mock_swarm = MagicMock()
        with patch('src.trading.trading_agents.Swarm', return_value=self.mock_swarm):
            self.trading_swarm = TradingSwarm(self.config)

    def test_initialization(self):
        """Test TradingSwarm initialization"""
        self.assertIsNotNone(self.trading_swarm.technical_agent)
        self.assertIsNotNone(self.trading_swarm.sentiment_agent)
        self.assertIsNotNone(self.trading_swarm.risk_agent)
        self.assertIsNotNone(self.trading_swarm.execution_agent)
        self.assertEqual(self.trading_swarm.config, self.config)

    def test_calculate_rsi_error_handling(self):
        """Test RSI calculation error handling"""
        # Test with invalid input type
        invalid_input = "not a dataframe or dict"
        self.assertIsNone(self.trading_swarm._calculate_rsi(invalid_input))

        # Test with missing close column
        invalid_df = pd.DataFrame({'open': [1.0, 2.0, 3.0]})
        self.assertIsNone(self.trading_swarm._calculate_rsi(invalid_df))

        # Test with insufficient data points
        short_df = pd.DataFrame({'close': [1.0, 2.0]})
        self.assertIsNone(self.trading_swarm._calculate_rsi(short_df))

        # Test with NaN values
        nan_df = pd.DataFrame({'close': [1.0, np.nan, 3.0, 4.0, 5.0]})
        rsi = self.trading_swarm._calculate_rsi(nan_df)
        self.assertIsNotNone(rsi)
        self.assertTrue(0 <= rsi <= 100)

    def test_calculate_rsi(self):
        """Test RSI calculation with different scenarios"""
        # Test normal case with increasing prices
        data = pd.DataFrame({
            'close': [10.0, 10.5, 11.0, 11.5, 12.0]
        })
        rsi = self.trading_swarm._calculate_rsi(data)
        self.assertIsNotNone(rsi)
        self.assertEqual(rsi, 100.0)  # All gains should give RSI of 100

        # Test with insufficient data
        short_df = pd.DataFrame({
            'close': [100.0, 101.0]
        })
        rsi = self.trading_swarm._calculate_rsi(short_df)
        self.assertIsNone(rsi)

        # Test with constant prices
        constant_df = pd.DataFrame({
            'close': [100.0] * 15
        })
        rsi = self.trading_swarm._calculate_rsi(constant_df)
        self.assertEqual(rsi, 50.0)  # Should be neutral

    def test_sentiment_methods(self):
        """Test sentiment analysis methods"""
        # Test news sentiment
        news_sentiment = self.trading_swarm._fetch_news_sentiment("AAPL")
        self.assertEqual(news_sentiment, 0.5)  # Default neutral sentiment

        # Test social sentiment
        social_sentiment = self.trading_swarm._fetch_social_sentiment("AAPL")
        self.assertEqual(social_sentiment, 0.5)  # Default neutral sentiment

        # Test sentiment aggregation
        aggregated_sentiment = self.trading_swarm._aggregate_sentiment()
        self.assertEqual(aggregated_sentiment, 0.5)  # Default neutral sentiment

    def test_parse_agent_response_edge_cases(self):
        """Test agent response parsing edge cases"""
        # Test with None response
        self.assertEqual(self.trading_swarm._parse_agent_response(None), {})

        # Test with empty messages
        empty_response = MagicMock()
        empty_response.messages = []
        self.assertEqual(self.trading_swarm._parse_agent_response(empty_response), {})

        # Test with None content
        none_content = MagicMock()
        none_content.messages = [{"content": None}]
        self.assertEqual(self.trading_swarm._parse_agent_response(none_content), {})

        # Test with invalid JSON in code block
        invalid_json_block = MagicMock()
        invalid_json_block.messages = [{"content": "```json\ninvalid json content\n```"}]
        result = self.trading_swarm._parse_agent_response(invalid_json_block)
        self.assertEqual(result["status"], "processed")

        # Test with markdown without JSON
        markdown = MagicMock()
        markdown.messages = [{"content": "# Analysis\nSome markdown content"}]
        result = self.trading_swarm._parse_agent_response(markdown)
        self.assertEqual(result["status"], "processed")

    def test_parse_agent_response(self):
        """Test agent response parsing"""
        # Test with dictionary response
        dict_response = MagicMock()
        dict_response.messages = [{"content": {"status": "success", "data": "test"}}]
        result = self.trading_swarm._parse_agent_response(dict_response)
        self.assertEqual(result, {"status": "success", "data": "test"})

        # Test with JSON string response
        json_response = MagicMock()
        json_response.messages = [{"content": '{"status": "success", "data": "test"}'}]
        result = self.trading_swarm._parse_agent_response(json_response)
        self.assertEqual(result, {"status": "success", "data": "test"})

        # Test with invalid JSON
        invalid_response = MagicMock()
        invalid_response.messages = [{"content": "invalid json"}]
        result = self.trading_swarm._parse_agent_response(invalid_response)
        self.assertEqual(result, {"status": "processed", "message": "invalid json"})

        # Test with empty response
        empty_response = MagicMock()
        empty_response.messages = []
        result = self.trading_swarm._parse_agent_response(empty_response)
        self.assertEqual(result, {})

    def test_check_risk_approval_edge_cases(self):
        """Test risk approval checking edge cases"""
        # Test with non-dict input
        self.assertFalse(self.trading_swarm._check_risk_approval("not a dict"))
        self.assertFalse(self.trading_swarm._check_risk_approval(None))

        # Test with empty dict
        self.assertFalse(self.trading_swarm._check_risk_approval({}))

        # Test with nested content structure
        nested_data = {
            "content": {
                "approved": True,
                "risk_parameters": {
                    "position_size_check": "Valid",
                    "portfolio_exposure_check": "Valid",
                    "stop_loss_level_check": "Valid",
                    "risk_reward_ratio_check": "Valid",
                    "compliance": "Approved"
                }
            }
        }
        self.assertTrue(self.trading_swarm._check_risk_approval(nested_data))

        # Test with invalid risk parameters
        invalid_params = {
            "approved": True,
            "risk_parameters": {
                "position_size_check": "Invalid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Approved"
            }
        }
        self.assertFalse(self.trading_swarm._check_risk_approval(invalid_params))

    def test_analyze_trading_opportunity_dataframe(self):
        """Test analyzing trading opportunity with DataFrame input"""
        # Mock successful responses from all agents
        mock_technical_response = MagicMock()
        mock_technical_response.messages = [{"content": {"signal": "buy", "confidence": 0.8}}]
        
        mock_sentiment_response = MagicMock()
        mock_sentiment_response.messages = [{"content": {"signal": "neutral", "confidence": 0.5}}]
        
        mock_risk_response = MagicMock()
        mock_risk_response.messages = [{"content": {
            "symbol": "AAPL",
            "trade": {
                "size": 10,
                "price": 103.0,
                "timestamp": "2024-01-05 00:00:00"
            },
            "risk_parameters": {
                "position_size_check": "Valid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Approved"
            },
            "approved": True
        }}]
        
        mock_execution_response = MagicMock()
        mock_execution_response.messages = [{"content": {
            "status": "executed",
            "price": 103.0,
            "size": 10,
            "timestamp": "2024-01-05"
        }}]

        # Set up the mock responses
        self.mock_swarm.run.side_effect = [
            mock_technical_response,
            mock_sentiment_response,
            mock_risk_response,
            mock_execution_response
        ]

        result = self.trading_swarm.analyze_trading_opportunity("AAPL", self.market_data_df)
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["price"], 103.0)

    def test_analyze_trading_opportunity_dict(self):
        """Test analyzing trading opportunity with dictionary input"""
        # Mock successful responses from all agents
        mock_technical_response = MagicMock()
        mock_technical_response.messages = [{"content": {"signal": "buy", "confidence": 0.8}}]
        
        mock_sentiment_response = MagicMock()
        mock_sentiment_response.messages = [{"content": {"signal": "neutral", "confidence": 0.5}}]
        
        mock_risk_response = MagicMock()
        mock_risk_response.messages = [{"content": {
            "symbol": "AAPL",
            "trade": {
                "size": 10,
                "price": 103.0,
                "timestamp": "2024-01-05"
            },
            "risk_parameters": {
                "position_size_check": "Valid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Approved"
            },
            "approved": True
        }}]
        
        mock_execution_response = MagicMock()
        mock_execution_response.messages = [{"content": {
            "status": "executed",
            "price": 103.0,
            "size": 10,
            "timestamp": "2024-01-05"
        }}]

        # Set up the mock responses
        self.mock_swarm.run.side_effect = [
            mock_technical_response,
            mock_sentiment_response,
            mock_risk_response,
            mock_execution_response
        ]

        result = self.trading_swarm.analyze_trading_opportunity("AAPL", self.market_data_dict)
        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["price"], 103.0)

    def test_analyze_trading_opportunity_empty_data(self):
        """Test analyzing trading opportunity with empty market data"""
        empty_data = {
            "close": [],
            "high": [],
            "low": [],
            "volume": [],
            "timestamp": []
        }
        result = self.trading_swarm.analyze_trading_opportunity("AAPL", empty_data)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "No price data available")

    def test_analyze_trading_opportunity_error_handling(self):
        """Test error handling in analyze_trading_opportunity"""
        # Test with invalid market data type
        result = self.trading_swarm.analyze_trading_opportunity("AAPL", "invalid data")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "Invalid market data type: str")

        # Test with technical analysis error
        mock_technical_response = MagicMock()
        mock_technical_response.messages = [{"content": {"error": "Technical analysis failed"}}]
        
        self.mock_swarm.run.side_effect = [mock_technical_response]
        
        result = self.trading_swarm.analyze_trading_opportunity("AAPL", self.market_data_dict)
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["reason"], "Technical analysis error: Technical analysis failed")

    def test_analyze_trading_opportunity_risk_rejected(self):
        """Test analyzing trading opportunity with risk rejection"""
        mock_technical_response = MagicMock()
        mock_technical_response.messages = [{"content": {"signal": "buy", "confidence": 0.8}}]
        
        mock_sentiment_response = MagicMock()
        mock_sentiment_response.messages = [{"content": {"signal": "neutral", "confidence": 0.5}}]
        
        mock_risk_response = MagicMock()
        mock_risk_response.messages = [{"content": {
            "symbol": "AAPL",
            "trade": {
                "size": 10,
                "price": 103.0,
                "timestamp": "2024-01-05"
            },
            "risk_parameters": {
                "position_size_check": "Invalid",
                "portfolio_exposure_check": "Valid",
                "stop_loss_level_check": "Valid",
                "risk_reward_ratio_check": "Valid",
                "compliance": "Rejected"
            },
            "approved": False,
            "reason": "Risk limits exceeded"
        }}]

        # Set up the mock responses
        self.mock_swarm.run.side_effect = [
            mock_technical_response,
            mock_sentiment_response,
            mock_risk_response
        ]

        result = self.trading_swarm.analyze_trading_opportunity("AAPL", self.market_data_dict)
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(result["reason"], "Risk limits exceeded")

    def test_check_daily_loss_limit(self):
        """Test daily loss limit checking"""
        result = self.trading_swarm._check_daily_loss_limit()
        self.assertTrue(result)  # Default implementation returns True

if __name__ == '__main__':
    unittest.main()
