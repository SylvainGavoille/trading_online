import requests
from textblob import TextBlob
import logging

class QualitativeAnalysis:
    def __init__(self, news_api_key, twitter_api_key, twitter_api_secret):
        """Initialize QualitativeAnalysis with API keys"""
        self.news_api_key = news_api_key
        self.twitter_api_key = twitter_api_key
        self.twitter_api_secret = twitter_api_secret
        self.logger = logging.getLogger(__name__)

    def fetch_news(self, symbol):
        """
        Fetch news articles for a given stock symbol.
        
        :param symbol: Stock symbol to fetch news for
        :return: Dictionary containing news articles
        """
        try:
            url = f"https://newsapi.org/v2/everything"
            params = {
                'q': symbol,
                'apiKey': self.news_api_key,
                'language': 'en',
                'sortBy': 'publishedAt'
            }
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching news for {symbol}: {e}")
            return {'articles': []}

    def fetch_twitter_data(self, symbol):
        """
        Fetch Twitter data for a given stock symbol.
        
        :param symbol: Stock symbol to fetch tweets for
        :return: Dictionary containing tweet data
        """
        try:
            url = "https://api.twitter.com/2/tweets/search/recent"
            headers = {
                'Authorization': f'Bearer {self.twitter_api_key}'
            }
            params = {
                'query': f'${symbol}',
                'max_results': 100
            }
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error fetching Twitter data for {symbol}: {e}")
            return {'data': []}

    def analyze_sentiment(self, text):
        """
        Analyze sentiment of a given text using TextBlob.
        
        :param text: Text to analyze
        :return: Sentiment polarity score (-1 to 1)
        """
        try:
            analysis = TextBlob(text)
            return analysis.sentiment.polarity
        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return 0

    def aggregate_sentiment(self, news_data, twitter_data):
        """
        Aggregate sentiment from news and Twitter data.
        
        :param news_data: Dictionary containing news articles
        :param twitter_data: Dictionary containing tweets
        :return: Aggregated sentiment score (-1 to 1)
        """
        try:
            sentiments = []

            # Analyze news sentiment
            for article in news_data.get('articles', []):
                title_sentiment = self.analyze_sentiment(article.get('title', ''))
                desc_sentiment = self.analyze_sentiment(article.get('description', ''))
                sentiments.extend([title_sentiment, desc_sentiment])

            # Analyze Twitter sentiment
            for tweet in twitter_data.get('data', []):
                tweet_sentiment = self.analyze_sentiment(tweet.get('text', ''))
                sentiments.append(tweet_sentiment)

            # Calculate average sentiment
            if sentiments:
                return sum(sentiments) / len(sentiments)
            return 0

        except Exception as e:
            self.logger.error(f"Error aggregating sentiment: {e}")
            return 0

    def get_qualitative_analysis(self, symbol):
        """
        Get overall qualitative analysis for a stock symbol.
        
        :param symbol: Stock symbol to analyze
        :return: Overall sentiment score (-1 to 1)
        """
        try:
            # Fetch data
            news_data = self.fetch_news(symbol)
            twitter_data = self.fetch_twitter_data(symbol)

            # Aggregate sentiment
            sentiment_score = self.aggregate_sentiment(news_data, twitter_data)

            self.logger.info(f"Qualitative analysis completed for {symbol}. Score: {sentiment_score}")
            return sentiment_score

        except Exception as e:
            self.logger.error(f"Error in qualitative analysis for {symbol}: {e}")
            return 0
