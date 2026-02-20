# Sentiment Analysis Setup

## Overview

In this tutorial, you'll learn how to set up and configure the sentiment analysis component of Quantum Trader. This powerful feature analyzes market sentiment from news and social media sources to enhance your trading decisions.

## Prerequisites

- Completed Technical Analysis Integration tutorial
- Basic understanding of YAML configuration
- API keys for news services (if using external providers)

## 1. Configuring News API Sources

The news analysis component processes market news to generate sentiment signals. Let's set up the news configuration:

1. Open your configuration file (`config/config.yaml`)
2. Add the following news analysis configuration:

```yaml
sentiment_analysis:
    news:
        update_interval: 300  # 5 minutes
        lookback_period: 86400  # 24 hours
        min_articles: 5
```

Key parameters:

- `update_interval`: How often to fetch new articles (in seconds)
- `lookback_period`: How far back to analyze news (in seconds)
- `min_articles`: Minimum number of articles needed for reliable sentiment

### Validation Steps

1. Start Quantum Trader in debug mode
2. Check the logs for successful news data fetching
3. Verify that sentiment scores are being generated

## 2. Setting Up Social Media Monitoring

Social media sentiment can provide early signals of market movements. Here's how to configure social media monitoring:

1. Add social media configuration to your config file:

```yaml
sentiment_analysis:
    social:
        update_interval: 180  # 3 minutes
        platforms: ["twitter", "reddit"]
        min_mentions: 10
```

Key parameters:

- `platforms`: List of social media platforms to monitor
- `min_mentions`: Minimum mentions needed for sentiment calculation
- `update_interval`: How often to refresh social media data

### Platform-Specific Setup

For each platform:

1. Configure API access (if using external services)
2. Set rate limits appropriately
3. Define relevant hashtags or keywords to track

## 3. Testing Sentiment Analysis Accuracy

To ensure your sentiment analysis is working correctly:

1. Configure the sentiment weights:

```yaml
sentiment_analysis:
    weights:
        news: 0.6
        social: 0.4
```

2. Run the built-in accuracy test:

```python
from src.trading.trading_agents import TradingSwarm

# Initialize trading swarm
config = load_config()
trading_swarm = TradingSwarm(config)

# Test sentiment analysis
sentiment_message = {
    "role": "user",
    "content": "Analyze market sentiment for AAPL. Return response as JSON."
}
sentiment_response = trading_swarm.client.run(
    agent=trading_swarm.sentiment_agent,
    messages=[sentiment_message]
)
```

3. Monitor these key metrics:
    - Signal accuracy
    - Response time
    - Error rates
    - Data availability

### Troubleshooting Common Issues

If you encounter issues:

1. Data Access Problems
    - Check API connectivity
    - Verify credentials
    - Monitor rate limits

2. Analysis Issues
    - Validate input data
    - Check scoring logic
    - Verify weight configurations

3. Integration Problems
    - Check signal format
    - Verify timing
    - Monitor system logs

## Best Practices

### 1. Data Collection

- Use multiple data sources for better accuracy
- Validate data quality regularly
- Monitor source reliability

### 2. Analysis Configuration

- Start with default weights
- Adjust based on performance
- Keep lookback periods reasonable

### 3. System Integration

- Monitor system logs
- Track sentiment accuracy
- Regularly backup configurations

## Next Steps

After completing this setup:

1. Monitor sentiment signals for your watchlist
2. Compare sentiment signals with price action
3. Adjust weights based on performance
4. Consider adding custom data sources

Remember: Sentiment analysis works best when combined with technical analysis and proper risk management. Use it as one of many inputs in your trading decisions.
