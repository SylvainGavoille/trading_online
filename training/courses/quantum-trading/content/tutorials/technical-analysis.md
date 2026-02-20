# Technical Analysis Integration

## Overview

The Quantum Trader platform implements several key technical indicators to help inform trading decisions. This tutorial will guide you through understanding and configuring these indicators for optimal trading performance.

## Core Technical Indicators

### 1. Moving Averages

The system implements two types of moving averages:

- **Simple Moving Average (SMA)**
    - Calculates the arithmetic mean of prices over a specified period
    - Default period: 20 days
    - Use case: Identifying trend direction and potential support/resistance levels

- **Exponential Moving Average (EMA)**
    - Gives more weight to recent prices
    - Default period: 20 days
    - Use case: More responsive to recent price changes than SMA

### 2. Relative Strength Index (RSI)

- Momentum oscillator measuring speed and magnitude of price changes
- Default period: 14 days
- Scale: 0 to 100
- Traditional interpretation:
    - Above 70: Potentially overbought
    - Below 30: Potentially oversold

### 3. MACD (Moving Average Convergence Divergence)

- Components:
    - Fast EMA (default: 12 periods)
    - Slow EMA (default: 26 periods)
    - Signal line (default: 9-period EMA of MACD)
- Use cases:
    - Trend direction identification
    - Momentum measurement
    - Signal generation through crossovers

### 4. Bollinger Bands

- Three bands showing price volatility:
    - Middle band: 20-period SMA
    - Upper band: SMA + (2 × standard deviation)
    - Lower band: SMA - (2 × standard deviation)
- Use cases:
    - Volatility measurement
    - Potential breakout identification
    - Overbought/oversold conditions

## Configuration Guide

### Basic Setup

1. Open your configuration file and locate the technical analysis section:

```yaml
technical_analysis:
    enabled: true
    indicators:
        sma:
            periods: [20, 50, 200]
        rsi:
            period: 14
            overbought: 70
            oversold: 30
        macd:
            fast_period: 12
            slow_period: 26
            signal_period: 9
        bollinger:
            period: 20
            std_dev: 2
```

### Advanced Configuration

#### Position Sizing Based on Technical Signals

```yaml
position_sizing:
    base_size: 100  # Base position size
    technical_multiplier:
        enabled: true
        max_multiplier: 2.0  # Maximum position size multiplier
        indicators:
            rsi_weight: 0.3
            macd_weight: 0.4
            bollinger_weight: 0.3
```

## Integration Examples

### 1. Basic Trend Following

```python
def check_trend_signals(rsi_value, macd_line, signal_line, current_price, sma_200):
    """
    Check multiple indicators for trend confirmation
    
    Args:
        rsi_value (float): Current RSI value
        macd_line (float): Current MACD line value
        signal_line (float): Current signal line value
        current_price (float): Current asset price
        sma_200 (float): 200-period SMA value
    
    Returns:
        bool: True if trend signals are positive
    """
    # Check for bullish conditions
    if (rsi_value > 50 and          # RSI above centerline
        macd_line > signal_line and  # MACD positive crossover
        current_price > sma_200):    # Price above 200 SMA
        return True
    return False
```

### 2. Mean Reversion Strategy

```python
def check_mean_reversion_signals(current_price, lower_band, upper_band, rsi_value):
    """
    Check Bollinger Bands and RSI for mean reversion signals
    
    Args:
        current_price (float): Current asset price
        lower_band (float): Lower Bollinger Band value
        upper_band (float): Upper Bollinger Band value
        rsi_value (float): Current RSI value
    
    Returns:
        int: 1 for long signal, -1 for short signal, 0 for no signal
    """
    if (current_price < lower_band and  # Price below lower band
        rsi_value < 30):               # RSI showing oversold
        return 1  # Long signal
    elif (current_price > upper_band and  # Price above upper band
          rsi_value > 70):               # RSI showing overbought
        return -1  # Short signal
    return 0  # No signal
```

## Best Practices

### 1. Indicator Combination

- Don't rely on a single indicator
- Look for confirmation across multiple indicators
- Consider different timeframes for validation

### 2. Parameter Optimization

- Test different parameter settings in paper trading
- Adjust parameters based on:
    - Asset volatility
    - Trading timeframe
    - Market conditions

### 3. Risk Management

- Use technical indicators for position sizing
- Set stop losses based on technical levels
- Monitor indicator divergences for potential reversals

## Exercises

1. Configure the technical analysis parameters for your trading style
2. Test different indicator combinations in paper trading mode
3. Document which indicator settings work best for different market conditions

## Next Steps

- Review the [Risk Management Integration](risk-management.md) tutorial
- Complete the [Advanced Trading Algorithms](algorithm-exercise.json) exercise
- Practice with paper trading using different technical setups

Remember that technical analysis should be part of a comprehensive trading strategy that includes fundamental analysis and proper risk management.
