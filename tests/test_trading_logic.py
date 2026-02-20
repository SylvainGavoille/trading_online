import unittest
from unittest.mock import patch, MagicMock
import logging
import pandas as pd
from src.trading.trading_logic import TradingLogic
from src.api.ib_connector import IBClient
from src.trading.agents.risk_validator import RiskValidator
from src.trading.agents.trade_executor import TradeExecutor
from src.trading.agents.signal_analyzer import SignalAnalyzer

class TestTradingLogic(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'api': {
                'tws_endpoint': 'localhost',
                'port': 7496
            },
            'risk_management': {
                'position_limits': {
                    'max_position_size': 100,
                    'max_portfolio_exposure': 0.25
                },
                'loss_limits': {
                    'daily_loss_limit': 1000
                },
                'stop_loss': {
                    'atr_multiplier': 2,
                    'max_loss_per_trade': 0.02
                },
                'trade_frequency': {
                    'max_daily_trades': 10
                }
            }
        }
        
        # Create market data with realistic values
        self.market_data = {
            'close': [150.25, 151.50, 149.75, 152.00, 151.25],
            'high': [151.00, 152.25, 150.50, 152.75, 152.00],
            'low': [149.50, 150.75, 149.00, 151.25, 150.50],
            'volume': [1000000, 1200000, 800000, 1500000, 1100000]
        }
        
        # Initialize mocks
        self.mock_api_connector = MagicMock(spec=IBClient)
        self.mock_risk_validator = MagicMock(spec=RiskValidator)
        self.mock_trade_executor = MagicMock(spec=TradeExecutor)
        self.mock_signal_analyzer = MagicMock(spec=SignalAnalyzer)
        
        # Initialize trading logic with mocks
        with patch('src.trading.trading_logic.IBClient') as mock_ib, \
             patch('src.trading.trading_logic.RiskValidator') as mock_rv, \
             patch('src.trading.trading_logic.TradeExecutor') as mock_te, \
             patch('src.trading.trading_logic.SignalAnalyzer') as mock_sa:
            mock_ib.return_value = self.mock_api_connector
            mock_rv.return_value = self.mock_risk_validator
            mock_te.return_value = self.mock_trade_executor
            mock_sa.return_value = self.mock_signal_analyzer
            self.trading_logic = TradingLogic(self.config)

    def test_execute_trade_success(self):
        """Test successful trade execution flow"""
        # Setup
        self.mock_api_connector.get_market_data.return_value = self.market_data
        self.mock_signal_analyzer.analyze_market_data.return_value = {
            'status': 'success',
            'technical_indicators': {
                'current_price': 151.25,
                'atr': 1.5,
                'price_target': 155.00,
                'stop_loss': 149.75
            }
        }
        self.mock_risk_validator.validate_trade.return_value = {
            'approved': True,
            'risk_parameters': {'compliance': 'Approved'}
        }
        self.mock_trade_executor.execute_trade.return_value = {
            'status': 'executed',
            'orders': {
                'main': {'order_id': '12345', 'status': 'filled'}
            }
        }
        
        # Execute
        result = self.trading_logic.execute_trade('AAPL', 'market', 10)
        
        # Verify component interaction flow
        self.assertIsNotNone(result)
        self.assertEqual(result['status'], 'executed')
        self.mock_api_connector.get_market_data.assert_called_once()
        self.mock_signal_analyzer.analyze_market_data.assert_called_once()
        self.mock_risk_validator.validate_trade.assert_called_once()
        self.mock_trade_executor.execute_trade.assert_called_once()

    def test_execute_trade_validation(self):
        """Test trade parameter validation"""
        # Test invalid quantity
        result = self.trading_logic.execute_trade('AAPL', 'market', 0)
        self.assertIsNone(result)
        self.mock_trade_executor.execute_trade.assert_not_called()
        
        # Test missing limit price
        result = self.trading_logic.execute_trade('AAPL', 'limit', 10)
        self.assertIsNone(result)
        self.mock_trade_executor.execute_trade.assert_not_called()

    def test_evaluate_trading_opportunity(self):
        """Test trading opportunity evaluation flow"""
        # Setup
        self.mock_signal_analyzer.analyze_market_data.return_value = {
            'status': 'success',
            'technical_indicators': {
                'current_price': 151.25,
                'atr': 1.5,
                'price_target': 155.00,
                'stop_loss': 149.75
            }
        }
        
        # Execute
        signal = self.trading_logic.evaluate_trading_opportunity('AAPL', self.market_data)
        
        # Verify component interaction
        self.assertIsNotNone(signal)
        self.assertTrue(-1 <= signal <= 1)
        self.mock_signal_analyzer.analyze_market_data.assert_called_once()

    def test_evaluate_trading_opportunity_validation(self):
        """Test trading opportunity input validation"""
        # Test with invalid inputs
        self.assertIsNone(self.trading_logic.evaluate_trading_opportunity('AAPL', None))
        self.assertIsNone(self.trading_logic.evaluate_trading_opportunity('AAPL', 'invalid'))
        self.mock_signal_analyzer.analyze_market_data.assert_not_called()

if __name__ == '__main__':
    unittest.main()
