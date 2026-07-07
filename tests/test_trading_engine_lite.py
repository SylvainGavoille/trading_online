import unittest
from unittest.mock import MagicMock, patch

from src.trading.agents.risk_validator import RiskValidator


class TestTradingEngineLiteTradeParams(unittest.TestCase):
    """Regression tests for the engine -> validator/executor trade_params contract.

    evaluate_trade() must emit the keys RiskValidator and TradeExecutor read
    ('size', 'target_price'), not the old 'quantity'/'take_profit'.
    """

    def setUp(self):
        self.config = {
            'risk_management': {
                'position_limits': {'max_position_size': 100, 'max_portfolio_exposure': 0.25},
                'stop_loss': {'atr_multiplier': 2, 'max_loss_per_trade': 0.02},
                'loss_limits': {'daily_loss_limit': 1000, 'max_drawdown': 0.15},
                'trade_frequency': {'max_daily_trades': 10},
                'risk_reward': {'min_ratio': 2.0, 'target_ratio': 3.0},
            },
            'agent_system': {
                'confidence_thresholds': {'technical': 0.5, 'combined': 0.5},
            },
        }
        # Build the engine without opening an IB connection.
        with patch('src.trading.trading_engine_lite.IBClient') as mock_ib_cls:
            from src.trading.trading_engine_lite import TradingEngineLite
            self.engine = TradingEngineLite(self.config)
        self.engine.ib_client = MagicMock()
        self.engine.ib_client.get_account_summary.return_value = {'NetLiquidation': 100000.0}

        self.analysis = {
            'status': 'success',
            'signal': 'BUY',
            'confidence': 0.8,
            'technical_score': 0.6,
            'indicators': {
                'price': 150.0,
                'bb_upper': 153.0,
                'bb_lower': 147.0,
            },
        }

    def test_evaluate_trade_emits_consumer_keys(self):
        """evaluate_trade returns 'size'/'target_price' and no stale keys."""
        tp = self.engine.evaluate_trade('AAPL', self.analysis)
        self.assertIsNotNone(tp)
        self.assertIn('size', tp)
        self.assertIn('target_price', tp)
        self.assertNotIn('quantity', tp)
        self.assertNotIn('take_profit', tp)

    def test_trade_params_validate_without_keyerror(self):
        """The engine's trade_params flow through RiskValidator with no KeyError."""
        tp = self.engine.evaluate_trade('AAPL', self.analysis)
        validator = RiskValidator(self.config)
        portfolio = {'total_value': 100000, 'daily_loss': 0, 'max_drawdown': 0.0}
        # Would raise KeyError on 'size'/'target_price' before the key alignment fix.
        result = validator.validate_trade(tp, portfolio)
        self.assertIn('approved', result)
        self.assertNotIn('Error during risk validation', str(result.get('reason', '')))


if __name__ == '__main__':
    unittest.main()
