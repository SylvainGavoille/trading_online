import unittest
import pandas as pd
import numpy as np
from src.analysis.technical_analysis import TechnicalAnalysis

class TestTechnicalAnalysis(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        # Create realistic test data
        self.test_data = pd.DataFrame({
            'close': [10, 10.5, 10.2, 10.8, 10.3, 10.6, 10.4, 10.9, 10.7, 10.5],
            'high':  [10.2, 10.8, 10.4, 11.0, 10.5, 10.8, 10.6, 11.1, 10.9, 10.7],
            'low':   [9.8, 10.3, 10.0, 10.6, 10.1, 10.4, 10.2, 10.7, 10.5, 10.3],
            'volume': [1000, 1500, 800, 2000, 900, 1300, 1100, 1800, 1400, 1200]
        })
        self.ta = TechnicalAnalysis(self.test_data)

    def test_evaluate_complete(self):
        """Test complete technical analysis evaluation"""
        result = self.ta.evaluate(self.test_data)
        self.assertIsNotNone(result)
        self.assertTrue(-1 <= result <= 1)

    def test_evaluate_empty_data(self):
        """Test evaluation with empty data"""
        empty_data = pd.DataFrame()
        result = self.ta.evaluate(empty_data)
        self.assertIsNone(result)

    def test_evaluate_missing_columns(self):
        """Test evaluation with missing required columns"""
        incomplete_data = pd.DataFrame({
            'close': [10, 11, 12],
            'volume': [1000, 1100, 1200]
        })
        result = self.ta.evaluate(incomplete_data)
        self.assertIsNone(result)

    def test_calculate_atr_wrapper(self):
        """Test ATR calculation wrapper method"""
        # Test with valid data
        atr = self.ta.calculate_atr('AAPL')  # Symbol parameter is ignored in implementation
        self.assertIsNotNone(atr)
        self.assertGreater(atr, 0)

        # Test with empty data
        empty_ta = TechnicalAnalysis(pd.DataFrame())
        atr = empty_ta.calculate_atr('AAPL')
        self.assertIsNone(atr)

        # Test with constant price data
        constant_data = pd.DataFrame({
            'close': [10.0] * 10,
            'high': [10.0] * 10,
            'low': [10.0] * 10,
            'volume': [1000] * 10
        })
        constant_ta = TechnicalAnalysis(constant_data)
        atr = constant_ta.calculate_atr('AAPL')
        self.assertIsNotNone(atr)
        self.assertAlmostEqual(atr, 0, delta=0.0001)

    def test_calculate_price_target(self):
        """Test price target calculation"""
        # Test with upward trend
        uptrend_data = pd.DataFrame({
            'close': [10, 10.2, 10.4, 10.6, 10.8],
            'high': [10.1, 10.3, 10.5, 10.7, 10.9],
            'low': [9.9, 10.1, 10.3, 10.5, 10.7],
            'volume': [1000] * 5
        })
        ta = TechnicalAnalysis(uptrend_data)
        target = ta.calculate_price_target('AAPL')  # Symbol parameter is ignored in implementation
        self.assertIsNotNone(target)
        self.assertGreater(target, uptrend_data['close'].iloc[-1])

        # Test with downward trend
        downtrend_data = pd.DataFrame({
            'close': [10.8, 10.6, 10.4, 10.2, 10.0],
            'high': [10.9, 10.7, 10.5, 10.3, 10.1],
            'low': [10.7, 10.5, 10.3, 10.1, 9.9],
            'volume': [1000] * 5
        })
        ta = TechnicalAnalysis(downtrend_data)
        target = ta.calculate_price_target('AAPL')
        self.assertIsNotNone(target)
        self.assertLess(target, downtrend_data['close'].iloc[-1])

        # Test with sideways trend
        sideways_data = pd.DataFrame({
            'close': [10.0] * 5,
            'high': [10.1] * 5,
            'low': [9.9] * 5,
            'volume': [1000] * 5
        })
        ta = TechnicalAnalysis(sideways_data)
        target = ta.calculate_price_target('AAPL')
        self.assertIsNotNone(target)
        self.assertAlmostEqual(target, sideways_data['close'].iloc[-1], delta=0.1)

        # Test with insufficient data
        insufficient_data = pd.DataFrame({
            'close': [10.0],
            'high': [10.1],
            'low': [9.9],
            'volume': [1000]
        })
        ta = TechnicalAnalysis(insufficient_data)
        target = ta.calculate_price_target('AAPL')
        self.assertIsNone(target)

    def test_sma_calculation(self):
        """Test Simple Moving Average calculation"""
        sma = self.ta.sma(3)
        expected = pd.Series([np.nan, np.nan, 10.23333, 10.50000, 10.43333, 
                            10.56667, 10.43333, 10.63333, 10.66667, 10.70000])
        pd.testing.assert_series_equal(sma.round(5), expected.round(5))

    def test_sma_insufficient_data(self):
        """Test SMA with insufficient data"""
        short_data = pd.DataFrame({
            'close': [10, 11]
        })
        ta = TechnicalAnalysis(short_data)
        sma = ta.sma(3)
        self.assertTrue(pd.isna(sma).all())

    def test_ema_calculation(self):
        """Test Exponential Moving Average calculation"""
        ema = self.ta.ema(3)
        expected = pd.Series([10.00000, 10.25000, 10.22500, 10.51250, 10.40625,
                            10.50313, 10.45156, 10.67578, 10.68789, 10.59395])
        pd.testing.assert_series_equal(ema.round(5), expected.round(5))

    def test_vwap_calculation(self):
        """Test Volume Weighted Average Price calculation"""
        vwap = self.ta.vwap(3)
        expected = pd.Series([np.nan, np.nan, 10.29091, 10.59535, 10.54865,
                            10.63095, 10.45152, 10.67619, 10.70698, 10.72727])
        pd.testing.assert_series_equal(vwap.round(5), expected.round(5))

    def test_rsi_calculation(self):
        """Test Relative Strength Index calculation"""
        rsi = self.ta.rsi(3)
        expected = pd.Series([np.nan, np.nan, np.nan, 78.57143, 42.85714,
                            64.28571, 30.00000, 80.00000, 55.55556, 55.55556])
        pd.testing.assert_series_equal(rsi.round(5), expected.round(5))

    def test_rsi_all_gains(self):
        """Test RSI with all price increases"""
        increasing_data = pd.DataFrame({
            'close': [10.0, 11.0, 12.0, 13.0, 14.0]
        })
        ta = TechnicalAnalysis(increasing_data)
        rsi = ta.rsi(3)
        self.assertTrue((rsi.fillna(100) == 100).all())

    def test_rsi_all_losses(self):
        """Test RSI with all price decreases"""
        decreasing_data = pd.DataFrame({
            'close': [14.0, 13.0, 12.0, 11.0, 10.0]
        })
        ta = TechnicalAnalysis(decreasing_data)
        rsi = ta.rsi(3)
        self.assertTrue((rsi.fillna(0) == 0).all())

    def test_macd_calculation(self):
        """Test MACD calculation"""
        macd_line, signal_line = self.ta.macd(3, 6, 3)
        expected_macd = pd.Series([0.00000, 0.10714, 0.06582, 0.17023, 0.07605,
                                 0.09584, 0.04636, 0.12921, 0.09748, 0.02937])
        expected_signal = pd.Series([0.00000, 0.05357, 0.05969, 0.11496, 0.09551,
                                   0.09567, 0.07102, 0.10011, 0.09880, 0.06408])
        pd.testing.assert_series_equal(macd_line.round(5), expected_macd.round(5))
        pd.testing.assert_series_equal(signal_line.round(5), expected_signal.round(5))

    def test_bollinger_bands_calculation(self):
        """Test Bollinger Bands calculation"""
        upper_band, lower_band = self.ta.bollinger_bands(3, 2)
        expected_upper = pd.Series([np.nan, np.nan, 10.73666, 11.10000, 11.07624,
                                  11.06999, 10.73884, 11.13666, 11.16999, 11.10000])
        expected_lower = pd.Series([np.nan, np.nan, 9.73001, 9.90000, 9.79042,
                                  10.06334, 10.12783, 10.13001, 10.16334, 10.30000])
        pd.testing.assert_series_equal(upper_band.round(5), expected_upper.round(5))
        pd.testing.assert_series_equal(lower_band.round(5), expected_lower.round(5))

    def test_bollinger_bands_constant_price(self):
        """Test Bollinger Bands with constant price"""
        constant_data = pd.DataFrame({
            'close': [10.0] * 10,
            'high': [10.0] * 10,
            'low': [10.0] * 10,
            'volume': [1000] * 10
        })
        ta = TechnicalAnalysis(constant_data)
        upper, lower = ta.bollinger_bands(3)
        self.assertTrue((upper == 10.0).all())
        self.assertTrue((lower == 10.0).all())

    def test_atr_calculation(self):
        """Test Average True Range calculation"""
        atr = self.ta.atr(3)
        expected = pd.Series([np.nan, np.nan, 0.56667, 0.70000, 0.66667,
                            0.66667, 0.53333, 0.53333, 0.50000, 0.50000])
        pd.testing.assert_series_equal(atr.round(5), expected.round(5))

    def test_adx_calculation(self):
        """Test Average Directional Index calculation"""
        adx = self.ta.adx(3)
        expected = pd.Series([np.nan, np.nan, np.nan, np.nan, np.nan,
                            34.28571, 27.61905, 42.85714, 37.03704, 27.40741])
        pd.testing.assert_series_equal(adx.round(5), expected.round(5))

    def test_cci_calculation(self):
        """Test Commodity Channel Index calculation"""
        cci = self.ta.cci(3)
        expected = pd.Series([np.nan, np.nan, np.nan, np.nan, -57.14286,
                            14.63415, -33.33333, 160.00000, 20.00000, -80.00000])
        pd.testing.assert_series_equal(cci.round(5), expected.round(5))

    def test_evaluate_strong_buy_signal(self):
        """Test evaluation with strong buy signals"""
        strong_buy_data = pd.DataFrame({
            'close': [10, 11, 12, 13, 14],
            'high': [10.5, 11.5, 12.5, 13.5, 14.5],
            'low': [9.5, 10.5, 11.5, 12.5, 13.5],
            'volume': [1000, 1200, 1400, 1600, 1800]
        })
        ta = TechnicalAnalysis(strong_buy_data)
        result = ta.evaluate(strong_buy_data)
        self.assertGreater(result, 0)

    def test_evaluate_strong_sell_signal(self):
        """Test evaluation with strong sell signals"""
        strong_sell_data = pd.DataFrame({
            'close': [14, 13, 12, 11, 10],
            'high': [14.5, 13.5, 12.5, 11.5, 10.5],
            'low': [13.5, 12.5, 11.5, 10.5, 9.5],
            'volume': [1800, 1600, 1400, 1200, 1000]
        })
        ta = TechnicalAnalysis(strong_sell_data)
        result = ta.evaluate(strong_sell_data)
        self.assertLess(result, 0)

    def test_evaluate_neutral_signal(self):
        """Test evaluation with neutral signals"""
        neutral_data = pd.DataFrame({
            'close': [10] * 5,
            'high': [10.5] * 5,
            'low': [9.5] * 5,
            'volume': [1000] * 5
        })
        ta = TechnicalAnalysis(neutral_data)
        result = ta.evaluate(neutral_data)
        self.assertAlmostEqual(result, 0, delta=0.1)

    def test_evaluate_extreme_volatility(self):
        """Test evaluation with extreme price volatility"""
        volatile_data = pd.DataFrame({
            'close': [10, 15, 5, 20, 2],
            'high': [12, 18, 8, 25, 5],
            'low': [8, 13, 3, 18, 1],
            'volume': [1000, 2000, 3000, 4000, 5000]
        })
        ta = TechnicalAnalysis(volatile_data)
        result = ta.evaluate(volatile_data)
        self.assertIsNotNone(result)
        self.assertTrue(-1 <= result <= 1)

if __name__ == '__main__':
    unittest.main()
