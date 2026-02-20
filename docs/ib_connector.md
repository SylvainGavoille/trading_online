# Interactive Brokers Connector Documentation

## Overview

The IB Connector module (`IBClient`) provides integration with Interactive Brokers' Trader Workstation (TWS) or IB Gateway. It handles market data streaming, connection management, and data synchronization.

## Class Structure

```python
class IBClient(EWrapper, EClient):
    """Interactive Brokers API Client"""
```

The `IBClient` class inherits from both `EWrapper` and `EClient` to provide a complete interface to the IB API.

## Initialization

```python
def __init__(self, config):
    """
    Initialize the IB client with configuration
    
    Args:
        config (dict): Configuration dictionary containing API settings
    """
```

Required configuration:

```yaml
api:
    tws_endpoint: "127.0.0.1"  # TWS/Gateway host
    port: 7497                 # TWS/Gateway port
```

## Connection Management

### Connecting to TWS/Gateway

```python
def connect_and_run(self):
    """
    Establish connection and start message processing thread
    
    Returns:
        bool: True if connection successful, False otherwise
    """
```

The connection process:

1. Establishes connection to TWS/Gateway
2. Starts message processing thread
3. Waits for initial connection messages
4. Returns connection status

### Error Handling

```python
def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
    """Handle error messages from TWS"""
```

Handles various error types:

- Connection status messages (2104, 2106, 2158)
- Security definition errors (200)
- Market data subscription errors (354)
- General errors

## Market Data Management

### Data Structure

The market data is stored in a synchronized structure:

```python
self.market_data = defaultdict(lambda: {
    'timestamp': [],    # Data timestamps
    'close': [],       # Close/last prices
    'high': [],        # High prices
    'low': [],         # Low prices
    'volume': [],      # Volume data
    'last_update': None,
    'current_high': None,
    'current_low': None
})
```

### Requesting Market Data

```python
def get_market_data(self, symbol):
    """
    Get market data for a symbol
    
    Args:
        symbol (str): Stock symbol
    
    Returns:
        dict: Market data dictionary or None if error
    """
```

The process:

1. Creates contract specification
2. Generates unique request ID
3. Requests delayed market data
4. Waits for data with timeout
5. Returns synchronized data structure

### Data Synchronization

The system ensures data synchronization through:

1. Centralized update method
2. Atomic operations with threading locks
3. Consistent timestamp alignment
4. Proper high/low tracking

```python
def _update_market_data(self, symbol, price, size=0):
    """
    Helper method to update market data ensuring synchronization
    
    Args:
        symbol (str): Stock symbol
        price (float): Current price
        size (int): Trade size
    """
```

### Price Updates

```python
def tickPrice(self, reqId, tickType, price, attrib):
    """Handle price updates"""
```

Handles various tick types:

- Last/close prices (4, 68, 9)
- High prices (6, 70)
- Low prices (7, 71)
- Bid/ask prices (1, 2, 65, 66)

### Volume Updates

```python
def tickSize(self, reqId, tickType, size):
    """Handle size/volume updates"""
```

Processes volume data:

- Trade volume (8, 72)
- Updates synchronized with price data

## Data Validation

The system implements several validation layers:

1. Price validation (must be > 0)
2. Data synchronization checks
3. Timeout handling
4. Error state management

## Best Practices

### Market Data Handling

1. Always use the synchronized update method
2. Check for valid prices before processing
3. Handle timeout conditions
4. Implement proper error recovery

### Connection Management

1. Monitor connection status
2. Handle reconnection scenarios
3. Validate market data subscriptions
4. Process error messages appropriately

## Error Recovery

The system implements various error recovery mechanisms:

1. Connection retry logic
2. Data resubscription
3. State recovery
4. Error logging and notification

## Configuration Example

```yaml
api:
    tws_endpoint: "127.0.0.1"
    port: 7497

market_data:
    timeout: 15
    retry_attempts: 3
    data_type: "delayed"  # or "realtime"
```

## Usage Example

```python
from src.api.ib_connector import IBClient

# Initialize client
config = {
    'api': {
        'tws_endpoint': '127.0.0.1',
        'port': 7497
    }
}
client = IBClient(config)

# Connect to TWS/Gateway
if client.connect_and_run():
    # Request market data
    market_data = client.get_market_data("AAPL")
    if market_data:
        print(f"Last price: {market_data['close'][-1]}")
```

## Troubleshooting

Common issues and solutions:

1. Connection Issues
    - Verify TWS/Gateway is running
    - Check port configuration
    - Confirm API permissions

2. Market Data Issues
    - Verify market data subscriptions
    - Check symbol validity
    - Confirm data type settings

3. Synchronization Issues
    - Check thread safety
    - Verify data structure integrity
    - Monitor update sequences

## Logging

The system provides detailed logging:

- Connection events
- Market data updates
- Error conditions
- System status changes

## Integration Notes

The IB Connector integrates with:

1. Trading system core
2. Market data processing
3. Order management
4. System monitoring

Always ensure proper synchronization and error handling when integrating with other system components.
