# System Setup Tutorial

## Overview

This tutorial will guide you through setting up your Quantum Trader development environment.

## Prerequisites

- Basic understanding of command line interfaces
- Administrator access to your computer

## Installation Steps

### 1. Python Installation

1. Visit python.org and download Python 3.10 or higher
2. Run the installer and ensure "Add Python to PATH" is checked
3. Verify installation by opening a terminal and running:

```bash
python --version
```

### 2. Repository Setup

1. Clone the repository:

```bash
git clone https://github.com/zoharbabin/quantum-trader.git
```

2. Navigate to the project directory:

```bash
cd quantum-trader
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. TWS/Gateway Configuration

1. Download and install TWS or IB Gateway from Interactive Brokers
2. Configure API settings:
    - Enable API connections
    - Set port to 7496 for TWS or 4001 for Gateway 
    - Add localhost to trusted IPs
3. Test connection using the provided test script

### 4. Verification

To verify your setup is complete:

1. Run the test suite:

```bash
python -m pytest tests/
```

2. Check system status:

```bash
python tools/check_setup.py
