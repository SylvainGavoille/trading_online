import argparse
import yaml
import logging
from datetime import datetime
import pandas as pd
import time
from src.trading.trading_agents import TradingSwarm
from src.api.ib_connector import IBClient

def setup_logging():
    """Setup logging configuration"""
    # Remove any existing handlers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        
    # Create a new handler
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Get logger and configure it
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    return logger

def load_config():
    """Load configuration from yaml file"""
    try:
        with open('src/config/config.yaml', 'r') as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError("Configuration file not found: src/config/config.yaml")

def check_ib_prerequisites():
    """Check and inform about IB TWS/Gateway prerequisites"""
    prerequisites = [
        "1. Interactive Brokers TWS or IB Gateway is running",
        "2. API connections are enabled in TWS/Gateway",
        "3. Socket port (default: 7497) is correctly configured",
        "4. Auto-restart is enabled in TWS/Gateway",
        "5. 'Read-Only API' is disabled in TWS/Gateway configuration"
    ]
    return prerequisites

def initialize_components(config, logger):
    """Initialize trading system components with error handling"""
    try:
        # Check prerequisites
        logger.info("Checking Interactive Brokers prerequisites...")
        prerequisites = check_ib_prerequisites()
        for prereq in prerequisites:
            logger.info(f"Prerequisite: {prereq}")

        # Initialize IB connection
        logger.info("Attempting to connect to Interactive Brokers...")
        ib_client = IBClient(config)
        
        # Try to connect with timeout
        connection_timeout = 10  # seconds
        connection_start = time.time()
        
        if not ib_client.connect_and_run():
            logger.error("Failed to establish connection to Interactive Brokers")
            logger.error("Please ensure all prerequisites are met:")
            for prereq in prerequisites:
                logger.error(f"  {prereq}")
            raise Exception("Failed to connect to Interactive Brokers")

        connection_time = time.time() - connection_start
        logger.info(f"Successfully connected to Interactive Brokers (took {connection_time:.2f} seconds)")

        # Initialize trading swarm
        trading_swarm = TradingSwarm(config)
        logger.info("Trading swarm initialized")

        return ib_client, trading_swarm

    except Exception as e:
        logger.error(f"Failed to initialize components: {str(e)}")
        raise

def process_market_data(market_data, symbol, logger):
    """Process and validate market data"""
    try:
        if market_data is None:
            raise ValueError("No price data")

        # Check for empty data
        if not market_data or not isinstance(market_data, dict):
            raise ValueError("Empty market data")

        # Check for missing or empty close prices
        if 'close' not in market_data or market_data['close'] is None:
            raise ValueError("No price data")
            
        if not market_data['close'] or len(market_data['close']) == 0:
            raise ValueError("Empty market data")
            
        if all(x is None for x in market_data['close']):
            raise ValueError("No price data")

        # Create a DataFrame with all available data points
        data = {
            'close': market_data['close'],
            'high': market_data.get('high', [None] * len(market_data['close'])),
            'low': market_data.get('low', [None] * len(market_data['close'])),
            'volume': market_data.get('volume', [0] * len(market_data['close']))
        }
        
        # Use timestamps if available, otherwise create timestamps
        timestamps = market_data.get('timestamp', [pd.Timestamp.now()] * len(market_data['close']))
        df = pd.DataFrame(data, index=pd.to_datetime(timestamps))

        # Validate the data
        if df.empty:
            raise ValueError("Empty market data")
        
        if df['close'].isnull().all():
            raise ValueError("No price data")

        return df

    except ValueError as e:
        logger.error(f"Error processing market data for {symbol}: {str(e)}")
        raise

def start_trading_system(config, symbols, logger):
    """Initialize and start the autonomous trading system"""
    ib_client = None
    try:
        # Initialize components
        ib_client, trading_swarm = initialize_components(config, logger)

        logger.info(f"Starting autonomous trading for symbols: {symbols}")
        logger.info("System Configuration:")
        logger.info(f"- Max Position Size: {config['risk_management']['position_limits']['max_position_size']}")
        logger.info(f"- Daily Loss Limit: {config['risk_management']['loss_limits']['daily_loss_limit']}")
        logger.info(f"- Update Interval: {config['agent_system']['update_interval']} seconds")

        # Trading loop
        while True:
            if not ib_client.isConnected():
                logger.error("Lost connection to Interactive Brokers. Attempting to reconnect...")
                if not ib_client.connect_and_run():
                    raise Exception("Failed to reconnect to Interactive Brokers")
                logger.info("Successfully reconnected to Interactive Brokers")

            for symbol in symbols:
                try:
                    # Fetch latest market data
                    market_data = ib_client.get_market_data(symbol)
                    
                    # Process and validate market data
                    df = process_market_data(market_data, symbol, logger)
                    
                    # Log market data summary
                    logger.info(f"Market data received for {symbol}:")
                    logger.info(f"- Latest Price: {df['close'].iloc[-1]:.2f}")
                    if not df['volume'].iloc[-1] != 0:
                        logger.info(f"- Volume: {df['volume'].iloc[-1]}")
                    if not pd.isna(df['high'].iloc[-1]):
                        logger.info(f"- High: {df['high'].iloc[-1]:.2f}")
                    if not pd.isna(df['low'].iloc[-1]):
                        logger.info(f"- Low: {df['low'].iloc[-1]:.2f}")
                    
                    # Analyze trading opportunity
                    result = trading_swarm.analyze_trading_opportunity(symbol, df)
                    
                    # Log analysis result
                    if result['status'] == 'executed':
                        logger.info(f"Trade executed for {symbol}:")
                        logger.info(f"- Price: {result['price']}")
                        logger.info(f"- Size: {result['size']}")
                        logger.info(f"- Timestamp: {result['timestamp']}")
                    elif result['status'] == 'rejected':
                        logger.info(f"Trade rejected for {symbol}: {result.get('reason', 'Unknown reason')}")
                    elif result['status'] == 'error':
                        logger.error(f"Error analyzing {symbol}: {result.get('reason', 'Unknown error')}")
                    
                except ValueError as ve:
                    logger.warning(f"Market data issue for {symbol}: {str(ve)}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing symbol {symbol}: {str(e)}")
                    continue

            # Wait for next update interval
            time.sleep(config['agent_system']['update_interval'])

    except KeyboardInterrupt:
        logger.info("Shutting down trading system...")
    except Exception as e:
        logger.error(f"Critical error in trading system: {str(e)}")
    finally:
        if ib_client is not None and ib_client.isConnected():
            logger.info("Disconnecting from Interactive Brokers...")
            ib_client.disconnect()
            logger.info("Disconnected successfully")

def main():
    parser = argparse.ArgumentParser(description="Autonomous Trading System CLI")
    parser.add_argument("--symbols", required=True, nargs='+',
                      help="List of symbols to trade (e.g., AAPL MSFT GOOGL)")
    parser.add_argument("--mode", choices=['live', 'paper'], default='paper',
                      help="Trading mode: 'live' or 'paper' trading")
    
    args = parser.parse_args()
    
    # Setup
    logger = setup_logging()
    config = load_config()
    
    # Update config based on mode
    config['trading_mode'] = args.mode
    
    # Log startup information
    logger.info("=== Quantum Trader Starting ===")
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Symbols: {args.symbols}")
    logger.info(f"Start Time: {datetime.now()}")
    
    # Start the trading system
    start_trading_system(config, args.symbols, logger)

if __name__ == "__main__":
    main()
