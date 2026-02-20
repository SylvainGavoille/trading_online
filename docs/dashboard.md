# Dashboard Documentation

## Overview

The dashboard provides a real-time, color-coded CLI interface for monitoring trading operations, market data, and system status. It offers multiple views and customizable layouts for efficient trading supervision.

## Display Components

### 1. Market Data Panel

Displays real-time market information:

- Current price
- Bid/Ask spread
- Volume
- Daily change
- 52-week high/low

Color coding:

- Green: Positive change
- Red: Negative change
- Yellow: No change
- White: Static information

### 2. Position Panel

Shows current positions:

```text
Symbol  Qty   Avg Cost  Curr Price  P&L      P&L%
AAPL    100   150.00   155.00      +500.00  +3.33%
GOOGL   50    2800.00  2795.00     -250.00  -0.18%
```

Color coding:

- Green: Profitable position
- Red: Loss-making position
- White: Neutral position

### 3. Order Panel

Displays active and recent orders:

```text
ID     Symbol  Type    Qty   Price   Status
12345  AAPL    MARKET  100   155.00  FILLED
12346  GOOGL   LIMIT   50    2800.00 PENDING
```

Status colors:

- Green: Filled
- Yellow: Pending
- Red: Rejected
- Blue: Partially filled

### 4. Technical Indicators

Shows real-time technical analysis:

- RSI
- MACD
- Bollinger Bands
- Moving Averages

Indicator alerts:

- Green: Buy signal
- Red: Sell signal
- Yellow: Neutral

### 5. Sentiment Analysis

Displays current market sentiment:

- News sentiment score
- Social media sentiment
- Combined sentiment indicator

Sentiment colors:

- Dark Green: Very positive
- Light Green: Positive
- Yellow: Neutral
- Light Red: Negative
- Dark Red: Very negative

### 6. System Status

Shows system health information:

- Connection status
- API rate limits
- Error counts
- System resources

Status colors:

- Green: Normal
- Yellow: Warning
- Red: Critical

## Layout Management

### Default Layout

```text
+----------------+----------------+
|  Market Data   |   Positions   |
+----------------+----------------+
|    Orders      |  Indicators   |
+----------------+----------------+
|   Sentiment    | System Status |
+----------------+----------------+
```

### Alternative Layouts

- Compact mode
- Full screen mode
- Focus mode (single panel)
- Custom arrangements

## Keyboard Controls

### Navigation

- Arrow keys: Move between panels
- Tab: Cycle through panels
- Enter: Select/Expand panel

### Commands

- 'q': Quit
- 'r': Refresh
- 'h': Help
- 'c': Clear alerts
- 'f': Toggle full screen
- 's': Save layout

### Panel-specific

- 'o': Sort orders
- 'p': Sort positions
- 'i': Change indicator timeframe
- 'm': Change market data view

## Configuration

### Color Scheme

```yaml
dashboard:
    colors:
        positive: "green"
        negative: "red"
        neutral: "white"
        warning: "yellow"
        info: "blue"
        background: "black"
```

### Layout Settings

```yaml
dashboard:
    layout:
        default_view: "standard"
        refresh_rate: 1
        timestamp_format: "%H:%M:%S"
        show_grid: true
```

### Alert Configuration

```yaml
dashboard:
    alerts:
        audio_enabled: true
        visual_enabled: true
        priority_levels:
            - critical
            - warning
            - info
```

## Performance

### Optimization

- Efficient screen updates
- Buffered output
- Async data updates
- Resource monitoring

### Rate Limiting

- Configurable refresh rates
- Smart update scheduling
- Bandwidth optimization

## Integration

The dashboard integrates with:

1. Market data feed
2. Order management system
3. Technical analysis module
4. Sentiment analysis
5. System monitoring

## Usage Example

```python
from src.cli.dashboard import Dashboard

# Initialize dashboard
dashboard = Dashboard(
    refresh_rate=1,
    layout="standard",
    color_enabled=True
)

# Start display
dashboard.start()

# Update specific panel
dashboard.update_market_data(new_data)
dashboard.update_positions(positions)
dashboard.update_orders(orders)

# Handle user input
dashboard.process_input()

# Stop display
dashboard.stop()
```

## Error Handling

### Display Errors

- Screen size constraints
- Terminal compatibility
- Color support issues

### Data Errors

- Missing data handling
- Update failures
- Connection issues

### Recovery

- Auto-refresh on error
- Fallback layouts
- Error notifications
