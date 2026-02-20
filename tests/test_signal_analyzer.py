import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, UTC
from src.trading.agents.signal_analyzer import SignalAnalyzer
from src.analysis.technical_analysis import TechnicalAnalysis

class TestSignalAnalyzer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_technical_analysis = MagicMock(spec=TechnicalAnalysis)
        self.signal_analyzer = SignalAnalyzer(self.mock_technical_analysis)
        
        # Sample market data
        self.market_data = {
            'close': [150.25, 151.50, 149.75, 152.00, 151.25],
            'high': [151.00, 152.25, 150.50, 152.75, 152.00],
            'low': [149.50, 150.75, 149.00, 151.25, 150.50],
            'volume': [1000000, 1200000, 800000, 1500000, 1100000],
            'timestamp': [
                datetime.now(UTC).isoformat() for _ in range(5)
            ]
        }

    def test_analyze_market_data_success(self):
        """Test successful market data analysis"""
        # Setup technical analysis mocks
        self.mock_technical_analysis.calculate_atr.return_value = 1.5
        self.mock_technical_analysis.calculate_price_target.return_value = 155.00
        
        # Execute
        result = self.signal_analyzer.analyze_market_data('AAPL', self.market_data)
        
        # Verify
        self.assertEqual(result['status'], 'success')
        self.assertIn('technical_indicators', result)
        self.assertIn('sentiment', result)
        
        # Verify technical indicators
        indicators = result['technical_indicators']
        self.assertAlmostEqual(indicators['current_price'], 151.25)
        self.assertAlmostEqual(indicators['atr'], 1.5)
        self.assertAlmostEqual(indicators['price_target'], 155.00)
        self.assertLess(indicators['stop_loss'], indicators['current_price'])

    def test_analyze_market_data_error_handling(self):
        """Test market data analysis error handling"""
        # Test various invalid inputs
        invalid_inputs = [
            None,  # None input
            'invalid',  # Invalid type
            {'close': [100.0]},  # Missing required columns
            pd.DataFrame()  # Empty DataFrame
        ]
        
        for data in invalid_inputs:
            result = self.signal_analyzer.analyze_market_data('AAPL', data)
            self.assertEqual(result['status'], 'error')

    def test_analyze_market_data_technical_failure(self):
        """Test analysis when technical indicators fail"""
        # Setup technical analysis to fail
        self.mock_technical_analysis.calculate_atr.return_value = None
        self.mock_technical_analysis.calculate_price_target.return_value = None
        
        # Execute
        result = self.signal_analyzer.analyze_market_data('AAPL', self.market_data)
        
        # Verify fallback values are used
        self.assertEqual(result['status'], 'success')
        indicators = result['technical_indicators']
        self.assertAlmostEqual(indicators['atr'], indicators['current_price'] * 0.01)
        self.assertAlmostEqual(indicators['price_target'], indicators['current_price'] * 1.02)

    def test_prepare_market_data(self):
        """Test market data preparation with different input types"""
        # Test DataFrame input
        df_input = pd.DataFrame(self.market_data)
        df_result = self.signal_analyzer._prepare_market_data(df_input)
        self.assertIsInstance(df_result, pd.DataFrame)
        self.assertTrue(all(col in df_result.columns for col in ['close', 'high', 'low', 'volume']))
        
        # Test dictionary input
        dict_result = self.signal_analyzer._prepare_market_data(self.market_data)
        self.assertIsInstance(dict_result, pd.DataFrame)
        self.assertTrue(all(col in dict_result.columns for col in ['close', 'high', 'low', 'volume']))
        
        # Test invalid input
        invalid_result = self.signal_analyzer._prepare_market_data("invalid")
        self.assertIsNone(invalid_result)

    def test_analyze_sentiment(self):
        """Test sentiment analysis"""
        result = self.signal_analyzer._analyze_sentiment('AAPL')
        
        # Verify structure and value ranges
        self.assertIn('news', result)
        self.assertIn('social', result)
        self.assertIn('aggregate', result)
        self.assertTrue(all(0 <= score <= 1 for score in result.values()))
        
        # Verify aggregate calculation
        expected_aggregate = result['news'] * 0.6 + result['social'] * 0.4
        self.assertAlmostEqual(result['aggregate'], expected_aggregate)

if __name__ == '__main__':
    unittest.main()
