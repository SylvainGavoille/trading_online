# Basic Operations Tutorial

## Overview

This tutorial will guide you through the basic operations of the Quantum Trader system.

## Prerequisites

- TWS/Gateway installed and configured
- Python environment set up
- Repository cloned and dependencies installed

## Basic Operations Guide

### 1. Starting the System

#### Launch TWS/Gateway

1. Open Interactive Brokers TWS or Gateway
2. Log in to your account
3. Ensure API connections are enabled in settings
4. Verify the connection port (7496 for TWS, 4001 for Gateway)

#### Start Paper Trading Mode

1. Open your terminal and navigate to the quantum-trader directory
2. Launch the system in paper trading mode:

```bash
python -m src.cli.cli_interface --symbols AAPL MSFT --mode paper
```

3. Verify successful connection in the terminal output

### 2. Monitoring System Output

#### Understanding Console Output

- Connection status messages
- Trade signals and execution reports
- System health indicators
- Performance metrics

#### Key Indicators to Watch

- Connection status
- Position updates
- Order status
- Error messages
- Trading signals

### 3. Command Line Interface

#### Basic Usage

```bash
python -m src.cli.cli_interface --symbols SYMBOLS [SYMBOLS ...] [--mode {live,paper}]
```

#### Required Arguments

- `--symbols`: List of symbols to trade (e.g., AAPL MSFT GOOGL)

#### Optional Arguments

- `--mode`: Trading mode, either 'live' or 'paper' trading (default: paper)

#### Examples

```bash
# Start paper trading with multiple symbols
python -m src.cli.cli_interface --symbols AAPL MSFT GOOGL --mode paper

# Start live trading with a single symbol
python -m src.cli.cli_interface --symbols AAPL --mode live
```

### 4. Troubleshooting

#### Common Issues

- Connection refused: Check if TWS/Gateway is running
- Authentication failed: Verify API settings
- Symbol not found: Check symbol validity
- Order rejected: Review account permissions

#### Resolution Steps

1. Check TWS/Gateway connection
2. Verify API settings
3. Review error logs
4. Consult documentation for specific error codes
