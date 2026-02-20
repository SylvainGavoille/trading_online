# CLI Interface Documentation

## Overview

The CLI interface provides a command-line tool for interacting with the Quantum Trader system. It handles market data processing, trading decisions, and system monitoring through a multi-agent architecture.

## Command Structure

### Basic Command Format

```bash
python -m src.cli.cli_interface --symbols SYMBOL1 SYMBOL2 ... --mode MODE
```

### Required Arguments

- `--symbols`: List of stock symbols to trade (e.g., AAPL MSFT GOOGL)
- `--mode`: Trading mode, either 'paper' or 'live' (default: paper)

## Prerequisites

Before starting the system, ensure:

1. Interactive Brokers TWS or IB Gateway is running
2. API connections are enabled in TWS/Gateway
3. Socket port (default: 7497) is correctly configured
4. Auto-restart is enabled in TWS/Gateway
5. 'Read-Only API' is disabled in TWS/Gateway configuration

## System Operation

### Starting the System

```bash
python -m src.cli.cli_interface --symbols AAPL MSFT GOOGL --mode paper
```

The system will:

1. Check all prerequisites
2. Connect to Interactive Brokers
3. Initialize the trading swarm
4. Begin market data processing
5. Start autonomous trading operations

### Market Data Processing

The system processes market data with:

- Real-time price updates
- Volume tracking
- High/low price monitoring
- Synchronized data management

### Trading Operations

The system operates through specialized agents:

1. Technical Analysis Agent
    - Analyzes market data using technical indicators
    - Provides technical-based trading signals

2. Sentiment Analysis Agent
    - Analyzes market sentiment
    - Provides sentiment-based signals

3. Risk Management Agent
    - Monitors position sizes and exposure
    - Enforces risk limits

4. Trade Execution Agent
    - Handles order placement
    - Manages trade execution

## System Output

The system provides detailed logging of:

- Connection status
- Market data updates
- Trading decisions
- Risk management actions
- System status

Example output:

```log
2024-11-10 18:24:20,523 - __main__ - INFO - === Quantum Trader Starting ===
2024-11-10 18:24:20,523 - __main__ - INFO - Mode: paper
2024-11-10 18:24:20,523 - __main__ - INFO - Symbols: ['AAPL', 'MSFT', 'GOOGL']
...
```

## Error Handling

The system handles various error conditions:

- Connection issues
- Market data problems
- Trading errors
- System failures

Error messages include:

- Clear error descriptions
- Relevant context
- Suggested solutions

## Configuration

The system uses a YAML configuration file (`src/config/config.yaml`) for:

- API settings
- Risk parameters
- Trading rules
- System behavior

Example configuration:

```yaml
api:
  tws_endpoint: "127.0.0.1"
  port: 7497

risk_management:
  position_limits:
    max_position_size: 100
  loss_limits:
    daily_loss_limit: 1000

agent_system:
  update_interval: 60
```

## Expected Behaviors

### Market Data Reception

- Regular price updates for each symbol
- Synchronized timestamp, price, and volume data
- Proper handling of market hours and data delays

### Trading Decisions

- Risk-based trade filtering
- Position size limits enforcement
- Trade rejection on risk limit violations

### System States

- Active: System is running and processing data
- Warning: System encounters non-critical issues
- Error: System encounters critical problems
- Shutdown: System is stopping operations

## Troubleshooting

Common issues and solutions:

1. Connection Problems
    - Verify TWS/Gateway is running
    - Check API connection settings
    - Confirm port configuration

2. Market Data Issues
    - Verify market data subscriptions
    - Check symbol validity
    - Confirm market hours

3. Trading Issues
    - Check risk limits
    - Verify account permissions
    - Confirm trading hours

## System Shutdown

To stop the system:

1. Press Ctrl+C for graceful shutdown
2. System will:
    - Close market data connections
    - Cancel pending orders (if any)
    - Disconnect from Interactive Brokers
    - Save system state
