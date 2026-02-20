import unittest
from unittest.mock import patch, MagicMock
from requests.exceptions import RequestException, HTTPError, Timeout
from src.analysis.qualitative_analysis import QualitativeAnalysis

class TestQualitativeAnalysis(unittest.TestCase):

    def setUp(self):
        self.qa = QualitativeAnalysis('fake_news_api_key', 'fake_twitter_api_key', 'fake_twitter_api_secret')
        self.sample_news_success = {
            'status': 'ok',
            'articles': [
                {
                    'title': 'Great earnings report for AAPL',
                    'description': 'Apple reports record quarterly revenue'
                },
                {
                    'title': 'Market analysis of tech stocks',
                    'description': 'Tech sector shows strong growth potential'
                }
            ]
        }
        self.sample_twitter_success = {
            'data': [
                {'text': 'AAPL stock is performing great! #bullish'},
                {'text': 'Not sure about $AAPL right now'},
                {'text': 'Bearish on Apple due to market conditions'}
            ]
        }

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_news_success(self, mock_get):
        """Test successful news API response"""
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_news_success
        mock_get.return_value = mock_response

        result = self.qa.fetch_news('AAPL')
        self.assertEqual(result, self.sample_news_success)
        
        # Verify correct API parameters
        mock_get.assert_called_with(
            'https://newsapi.org/v2/everything',
            params={
                'q': 'AAPL',
                'apiKey': 'fake_news_api_key',
                'language': 'en',
                'sortBy': 'publishedAt'
            }
        )

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_news_network_error(self, mock_get):
        """Test news API network error handling"""
        mock_get.side_effect = RequestException("Network error")
        result = self.qa.fetch_news('AAPL')
        self.assertEqual(result, {'articles': []})

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_news_timeout(self, mock_get):
        """Test news API timeout handling"""
        mock_get.side_effect = Timeout("Request timed out")
        result = self.qa.fetch_news('AAPL')
        self.assertEqual(result, {'articles': []})

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_news_rate_limit(self, mock_get):
        """Test news API rate limiting handling"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("429 Rate limit exceeded")
        mock_get.return_value = mock_response
        result = self.qa.fetch_news('AAPL')
        self.assertEqual(result, {'articles': []})

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_twitter_data_success(self, mock_get):
        """Test successful Twitter API response"""
        mock_response = MagicMock()
        mock_response.json.return_value = self.sample_twitter_success
        mock_get.return_value = mock_response

        result = self.qa.fetch_twitter_data('AAPL')
        self.assertEqual(result, self.sample_twitter_success)
        
        # Verify correct API parameters
        mock_get.assert_called_with(
            'https://api.twitter.com/2/tweets/search/recent',
            headers={'Authorization': 'Bearer fake_twitter_api_key'},
            params={'query': '$AAPL', 'max_results': 100}
        )

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_twitter_data_network_error(self, mock_get):
        """Test Twitter API network error handling"""
        mock_get.side_effect = RequestException("Network error")
        result = self.qa.fetch_twitter_data('AAPL')
        self.assertEqual(result, {'data': []})

    @patch('src.analysis.qualitative_analysis.requests.get')
    def test_fetch_twitter_data_rate_limit(self, mock_get):
        """Test Twitter API rate limiting handling"""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("429 Rate limit exceeded")
        mock_get.return_value = mock_response
        result = self.qa.fetch_twitter_data('AAPL')
        self.assertEqual(result, {'data': []})

    def test_analyze_sentiment_positive(self):
        """Test sentiment analysis with positive text"""
        test_cases = [
            ("This stock is performing excellently!", 0.5),  # Adjusted threshold
            ("Great earnings and strong growth", 0.3),      # Adjusted threshold
            ("Positive outlook for the company", 0.1)       # Adjusted threshold
        ]
        for text, expected_min in test_cases:
            sentiment = self.qa.analyze_sentiment(text)
            self.assertGreater(sentiment, expected_min)

    def test_analyze_sentiment_negative(self):
        """Test sentiment analysis with negative text"""
        test_cases = [
            ("This stock is performing poorly", -0.3),      # Adjusted threshold
            ("Terrible earnings and weak guidance", -0.4),  # Adjusted threshold
            ("Negative market conditions affecting growth", -0.1)  # Adjusted threshold
        ]
        for text, expected_max in test_cases:
            sentiment = self.qa.analyze_sentiment(text)
            self.assertLess(sentiment, expected_max)

    def test_analyze_sentiment_neutral(self):
        """Test sentiment analysis with neutral text"""
        test_cases = [
            "The stock price remained unchanged",
            "Market closed at the same level",
            "Trading volume was average today"
        ]
        for text in test_cases:
            sentiment = self.qa.analyze_sentiment(text)
            self.assertAlmostEqual(sentiment, 0, delta=0.3)

    def test_analyze_sentiment_empty_input(self):
        """Test sentiment analysis with empty input"""
        sentiment = self.qa.analyze_sentiment("")
        self.assertEqual(sentiment, 0)

    def test_aggregate_sentiment_mixed_data(self):
        """Test sentiment aggregation with mixed positive/negative data"""
        news_data = {
            'articles': [
                {'title': 'Great earnings report', 'description': 'Company exceeds expectations'},
                {'title': 'Market concerns', 'description': 'Potential challenges ahead'},
                {'title': 'Neutral market analysis', 'description': 'Stock trading sideways'}
            ]
        }
        twitter_data = {
            'data': [
                {'text': 'Bullish on this stock! #investing'},
                {'text': 'Not convinced about the growth prospects'},
                {'text': 'Market seems uncertain right now'}
            ]
        }
        sentiment_score = self.qa.aggregate_sentiment(news_data, twitter_data)
        self.assertTrue(-0.5 <= sentiment_score <= 0.5)

    def test_aggregate_sentiment_empty_data(self):
        """Test sentiment aggregation with empty data"""
        news_data = {'articles': []}
        twitter_data = {'data': []}
        sentiment_score = self.qa.aggregate_sentiment(news_data, twitter_data)
        self.assertEqual(sentiment_score, 0)

    @patch('src.analysis.qualitative_analysis.QualitativeAnalysis.fetch_news')
    @patch('src.analysis.qualitative_analysis.QualitativeAnalysis.fetch_twitter_data')
    def test_get_qualitative_analysis_integration(self, mock_fetch_twitter, mock_fetch_news):
        """Test complete qualitative analysis pipeline"""
        # Setup mock responses with real-world like data
        mock_fetch_news.return_value = {
            'articles': [
                {
                    'title': 'AAPL Q3 Earnings Beat Expectations',
                    'description': 'Apple reports strong iPhone sales and service revenue growth'
                },
                {
                    'title': 'Supply Chain Concerns for Apple',
                    'description': 'Global chip shortage may impact production'
                }
            ]
        }
        mock_fetch_twitter.return_value = {
            'data': [
                {'text': '$AAPL crushing it with iPhone sales! Very bullish'},
                {'text': 'Concerned about $AAPL supply chain issues'},
                {'text': 'Apple services showing strong growth potential'}
            ]
        }

        # Test the complete pipeline
        sentiment_score = self.qa.get_qualitative_analysis('AAPL')
        
        # Verify the pipeline executed completely
        mock_fetch_news.assert_called_once_with('AAPL')
        mock_fetch_twitter.assert_called_once_with('AAPL')
        
        # Verify sentiment score is within reasonable range
        self.assertTrue(-1 <= sentiment_score <= 1)

    @patch('src.analysis.qualitative_analysis.QualitativeAnalysis.fetch_news')
    @patch('src.analysis.qualitative_analysis.QualitativeAnalysis.fetch_twitter_data')
    def test_get_qualitative_analysis_api_failures(self, mock_fetch_twitter, mock_fetch_news):
        """Test qualitative analysis resilience to API failures"""
        # Simulate both APIs failing
        mock_fetch_news.return_value = {'articles': []}
        mock_fetch_twitter.return_value = {'data': []}

        sentiment_score = self.qa.get_qualitative_analysis('AAPL')
        self.assertEqual(sentiment_score, 0)

if __name__ == '__main__':
    unittest.main()
