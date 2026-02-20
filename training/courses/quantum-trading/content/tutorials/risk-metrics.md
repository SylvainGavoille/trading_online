# Understanding Risk Metrics

## Overview

This tutorial builds upon basic risk management concepts to introduce more advanced risk metrics used in portfolio management. Understanding these metrics is crucial for configuring advanced risk parameters in your trading system.

## 1. Portfolio Exposure

### What is Portfolio Exposure?

Portfolio exposure represents your total market risk across all positions. There are two key types:

1. **Gross Exposure**
    - Sum of all position values (long + short)
    - Example: Long $6000 + Short $4000 = $10,000 gross exposure
    - Formula:

```python
def calculate_gross_exposure(positions, account_value):
    """
    Calculate gross exposure as a ratio of account value
    
    Args:
        positions (list): List of position dictionaries
        account_value (float): Total account value
    
    Returns:
        float: Gross exposure ratio
    """
    total = sum(abs(pos['value']) for pos in positions)
    return total / account_value
```

2. **Net Exposure**
    - Difference between long and short positions
    - Example: Long $6000 - Short $4000 = $2,000 net exposure
    - Indicates directional bias of portfolio

### Why Exposure Matters

- Controls overall market risk
- Prevents overconcentration
- Maintains diversification
- Helps manage correlation risk

## 2. Understanding Drawdown

### What is Drawdown?

Drawdown measures the decline from a peak in portfolio value to a subsequent trough.

### Types of Drawdown

1. **Maximum Drawdown (MDD)**
    - Largest peak-to-trough decline
    - Key risk metric for strategy evaluation

```python
def calculate_max_drawdown(equity_curve):
    """
    Calculate maximum drawdown from an equity curve
    
    Args:
        equity_curve (list): List of portfolio values over time
    
    Returns:
        float: Maximum drawdown as a percentage
    """
    peak = equity_curve[0]
    max_dd = 0
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (peak - value) / peak
        max_dd = max(max_dd, dd)
    return max_dd
```

2. **Daily Drawdown**
    - Peak-to-trough decline within a trading day
    - Used for daily risk monitoring

### Managing Drawdown

- Set maximum drawdown limits
- Use trailing stops
- Reduce position sizes during drawdowns
- Implement recovery rules

## 3. Daily Loss Limits

### Purpose

- Prevent catastrophic losses
- Force trading breaks
- Maintain emotional control
- Preserve capital

### Implementation

1. **Fixed Dollar Amount**

```python
def check_daily_loss_limit(pnl, limit):
    """
    Check if daily loss limit has been exceeded
    
    Args:
        pnl (float): Current profit/loss
        limit (float): Maximum loss limit
    
    Returns:
        bool: True if limit exceeded, False otherwise
    """
    return abs(pnl) >= limit
```

2. **Percentage of Account**

```python
def check_daily_loss_percent(pnl, account_value, limit_percent):
    """
    Check if daily percentage loss limit has been exceeded
    
    Args:
        pnl (float): Current profit/loss
        account_value (float): Total account value
        limit_percent (float): Maximum loss percentage
    
    Returns:
        bool: True if limit exceeded, False otherwise
    """
    return abs(pnl) / account_value >= limit_percent
```

### Best Practices

1. Start with conservative limits
2. Consider market volatility
3. Account for trading style
4. Implement automatic stops

## 4. Value at Risk (VaR)

### Understanding VaR

- Statistical measure of potential loss
- Based on historical volatility
- Specified confidence level
- Time horizon (typically 1 day)

### Calculation Methods

1. **Historical VaR**

```python
def calculate_historical_var(returns, confidence_level):
    """
    Calculate VaR using historical method
    
    Args:
        returns (list): Historical returns
        confidence_level (float): e.g., 0.95 for 95%
    
    Returns:
        float: VaR value
    """
    return -np.percentile(returns, (1 - confidence_level) * 100)
```

2. **Parametric VaR**
    - Assumes normal distribution
    - Uses standard deviation
    - Simpler but less accurate

### Using VaR

- Set position limits
- Allocate risk capital
- Monitor portfolio risk
- Stress test strategies

## 5. Putting It All Together

### Risk Dashboard Example

```python
def generate_risk_metrics(portfolio):
    """
    Generate comprehensive risk metrics for a portfolio
    
    Args:
        portfolio (Portfolio): Portfolio object with positions and history
    
    Returns:
        dict: Dictionary of risk metrics
    """
    return {
        'gross_exposure': calculate_gross_exposure(portfolio.positions),
        'net_exposure': calculate_net_exposure(portfolio.positions),
        'current_drawdown': calculate_current_drawdown(portfolio.equity_curve),
        'daily_pnl': calculate_daily_pnl(portfolio),
        'var_95': calculate_var(portfolio.returns, 0.95)
    }
```

### Risk Limits Matrix

```yaml
risk_limits:
    exposure:
        gross_max: 1.5    # 150% of account
        net_max: 0.8      # 80% of account
    drawdown:
        max_allowed: 0.15 # 15% maximum drawdown
        daily_max: 0.05   # 5% daily maximum
    var:
        confidence: 0.95  # 95% confidence level
        limit: 0.02       # 2% of portfolio
```

## Practice Exercises

1. Calculate portfolio exposure:
    - Account value: $100,000
    - Long positions: $60,000
    - Short positions: $40,000
    - Calculate gross and net exposure

2. Analyze drawdown scenario:
    - Starting value: $100,000
    - Lowest value: $85,000
    - Calculate maximum drawdown percentage

3. Set appropriate limits:
    - Given your trading style
    - Account size
    - Risk tolerance
    - Market conditions

## Next Steps

- Implement risk metrics monitoring
- Set up alerts for limit breaches
- Practice calculating metrics
- Review and adjust limits regularly

Remember: These metrics work together to provide a comprehensive view of portfolio risk. Understanding their relationships is crucial for effective risk management.
