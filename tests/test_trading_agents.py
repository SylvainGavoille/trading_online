import unittest
from unittest.mock import patch, MagicMock
import pandas as pd

from src.trading.trading_agents import TradingSystemDSPy


class TestTradingSystemDSPy(unittest.TestCase):
    def setUp(self):
        """Initialize a TradingSystemDSPy with the LLM layer mocked out."""
        self.config = {
            "risk_management": {
                "position_limits": {
                    "max_position_size": 100,
                    "max_portfolio_exposure": 0.1,
                },
                "loss_limits": {
                    "daily_loss_limit": 1000,
                    "max_drawdown": 0.2,
                },
                "risk_reward": {"min_ratio": 2.0},
            }
        }

        # Sample OHLCV data (>= 5 rows so _format_market_data uses it).
        self.market_data_df = pd.DataFrame(
            {
                "open": [99.0, 100.0, 101.0, 100.5, 102.0],
                "high": [101.0, 102.0, 103.0, 102.5, 104.0],
                "low": [99.0, 100.0, 101.0, 100.5, 102.0],
                "close": [100.0, 101.0, 102.0, 101.5, 103.0],
                "volume": [1000, 1100, 1200, 1150, 1300],
            },
            index=pd.date_range(start="2024-01-01", periods=5),
        )

        self.indicators = {
            "rsi": 55.0,
            "macd": 0.5,
            "price": 103.0,
            "sma_20": 101.0,
        }

        # _configure_llm calls dspy.LM / dspy.configure; patch them so no real
        # LLM is contacted during construction.
        with patch("src.trading.trading_agents.dspy.LM", return_value=MagicMock()), patch(
            "src.trading.trading_agents.dspy.configure"
        ):
            self.system = TradingSystemDSPy(
                self.config, llm_provider="ollama", model="deepseek-r1:14b"
            )

    def test_initialization(self):
        """The system wires up the three DSPy agents and keeps the config."""
        self.assertIsNotNone(self.system.technical_agent)
        self.assertIsNotNone(self.system.sentiment_agent)
        self.assertIsNotNone(self.system.risk_agent)
        self.assertEqual(self.system.config, self.config)

    def test_analyze_technical_success(self):
        """analyze_technical parses the DSPy prediction into a result dict."""
        prediction = MagicMock()
        prediction.signal = "BUY"
        prediction.confidence = 0.82
        prediction.reasoning = "Strong upward momentum"
        self.system.technical_agent = MagicMock(return_value=prediction)

        result = self.system.analyze_technical("AAPL", self.market_data_df, self.indicators)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["confidence"], 0.82)
        self.assertEqual(result["reasoning"], "Strong upward momentum")

        # The agent receives formatted market_data + indicators strings.
        call_kwargs = self.system.technical_agent.call_args.kwargs
        self.assertIn("market_data", call_kwargs)
        self.assertIn("indicators", call_kwargs)

    def test_analyze_technical_error(self):
        """analyze_technical returns an error dict when the agent raises."""
        self.system.technical_agent = MagicMock(side_effect=RuntimeError("LLM down"))

        result = self.system.analyze_technical("AAPL", self.market_data_df, self.indicators)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["signal"], "NEUTRAL")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("LLM down", result["error"])

    def test_analyze_sentiment_success(self):
        """analyze_sentiment parses the DSPy prediction into a result dict."""
        prediction = MagicMock()
        prediction.sentiment = "BULLISH"
        prediction.confidence = 0.7
        prediction.key_factors = "Positive earnings"
        self.system.sentiment_agent = MagicMock(return_value=prediction)

        news = [{"title": "Beat earnings", "summary": "Q1 strong"}]
        social = [{"platform": "X", "text": "to the moon"}]
        result = self.system.analyze_sentiment("AAPL", news_data=news, social_data=social)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["symbol"], "AAPL")
        self.assertEqual(result["sentiment"], "BULLISH")
        self.assertEqual(result["confidence"], 0.7)
        self.assertEqual(result["key_factors"], "Positive earnings")

    def test_analyze_sentiment_error(self):
        """analyze_sentiment returns an error dict when the agent raises."""
        self.system.sentiment_agent = MagicMock(side_effect=ValueError("bad parse"))

        result = self.system.analyze_sentiment("AAPL")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["sentiment"], "NEUTRAL")
        self.assertEqual(result["confidence"], 0.0)
        self.assertIn("bad parse", result["error"])

    def test_validate_risk_success(self):
        """validate_risk parses the DSPy prediction into a result dict."""
        prediction = MagicMock()
        prediction.approved = True
        prediction.risk_score = 0.3
        prediction.reason = "Within limits"
        self.system.risk_agent = MagicMock(return_value=prediction)

        trade_params = {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "price": 103.0,
            "stop_loss": 100.0,
        }
        portfolio = {"total_value": 10000, "cash": 5000, "positions": []}
        result = self.system.validate_risk(trade_params, portfolio)

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["approved"])
        self.assertEqual(result["risk_score"], 0.3)
        self.assertEqual(result["reason"], "Within limits")

    def test_validate_risk_error(self):
        """validate_risk returns a rejecting error dict when the agent raises."""
        self.system.risk_agent = MagicMock(side_effect=RuntimeError("timeout"))

        result = self.system.validate_risk({}, {})

        self.assertEqual(result["status"], "error")
        self.assertFalse(result["approved"])
        self.assertEqual(result["risk_score"], 1.0)
        self.assertIn("timeout", result["reason"])


if __name__ == "__main__":
    unittest.main()
