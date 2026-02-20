import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC, timedelta
from src.trading.agents.risk_validator import RiskValidator

class TestRiskValidator(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'risk_management': {
                'position_limits': {
                    'max_position_size': 100,
                    'max_portfolio_exposure': 0.25
                },
                'stop_loss': {
                    'atr_multiplier': 2,
                    'max_loss_per_trade': 0.02
                },
                'loss_limits': {
                    'daily_loss_limit': 1000
                },
                'trade_frequency': {
                    'max_daily_trades': 10
                },
                'risk_reward': {
                    'min_ratio': 2.0
                }
            }
        }
        self.risk_validator = RiskValidator(self.config)
        
        # Common test parameters
        self.trade_params = {
            'symbol': 'AAPL',
            'size': 50,
            'price': 150.00,
            'stop_loss': 148.50,
            'target_price': 155.00
        }
        self.portfolio = {
            'total_value': 100000,
            'daily_loss': 500
        }

    def test_config_validation(self):
        """Test configuration validation"""
        # Test with missing required sections
        invalid_config = {
            'risk_management': {
                'position_limits': {}
            }
        }
        with self.assertRaises(ValueError):
            RiskValidator(invalid_config)

    def test_risk_validation_flow(self):
        """Test complete risk validation flow"""
        # Test successful validation
        result = self.risk_validator.validate_trade(self.trade_params, self.portfolio)
        self.assertTrue(result['approved'])
        self.assertEqual(result['risk_parameters']['compliance'], 'Approved')
        
        # Test cascading validation failure
        # Modify trade params to fail multiple checks
        invalid_trade = self.trade_params.copy()
        invalid_trade.update({
            'size': 150,  # Exceeds position limit
            'stop_loss': 145.00,  # Exceeds loss limit
            'target_price': 151.00  # Poor risk/reward ratio
        })
        
        result = self.risk_validator.validate_trade(invalid_trade, self.portfolio)
        self.assertFalse(result['approved'])
        self.assertEqual(result['risk_parameters']['position_size_check'], 'Invalid')

    def test_trade_frequency_tracking(self):
        """Test trade frequency tracking and cleanup"""
        symbol = 'AAPL'
        
        # Test frequency tracking
        for _ in range(5):
            self.risk_validator._record_trade(symbol)
        
        self.assertEqual(len(self.risk_validator.trade_history[symbol]), 5)
        
        # Test trade expiration
        old_time = datetime.now(UTC) - timedelta(days=2)
        self.risk_validator.trade_history[symbol] = [old_time] * 5
        
        # Add new trade
        self.risk_validator._record_trade(symbol)
        
        # Verify old trades are cleaned up
        self.assertEqual(len(self.risk_validator.trade_history[symbol]), 1)
        
        # Verify frequency check
        result = self.risk_validator._check_trade_frequency(symbol)
        self.assertTrue(result['approved'])

    def test_risk_reward_scenarios(self):
        """Test various risk/reward scenarios"""
        # Test optimal risk/reward
        trade = self.trade_params.copy()
        trade.update({
            'price': 100.00,
            'stop_loss': 99.00,
            'target_price': 103.00  # 1:3 risk/reward ratio
        })
        result = self.risk_validator._check_risk_reward_ratio(trade)
        self.assertTrue(result['approved'])
        
        # Test borderline case
        trade['target_price'] = 102.00  # 1:2 risk/reward ratio
        result = self.risk_validator._check_risk_reward_ratio(trade)
        self.assertTrue(result['approved'])
        
        # Test invalid case
        trade['target_price'] = 101.00  # 1:1 risk/reward ratio
        result = self.risk_validator._check_risk_reward_ratio(trade)
        self.assertFalse(result['approved'])

    def test_portfolio_risk_limits(self):
        """Test portfolio-wide risk limits"""
        # Test exposure limits
        large_trade = self.trade_params.copy()
        large_trade['size'] = 200  # Would exceed max exposure
        
        result = self.risk_validator._check_portfolio_exposure(
            large_trade,
            {'total_value': 100000}
        )
        self.assertFalse(result['approved'])
        
        # Test daily loss limits
        result = self.risk_validator._check_daily_loss_limit(
            {'daily_loss': 1500}  # Exceeds daily limit
        )
        self.assertFalse(result['approved'])

if __name__ == '__main__':
    unittest.main()
