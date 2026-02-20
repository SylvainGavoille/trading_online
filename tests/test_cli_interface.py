import unittest
from unittest.mock import patch, MagicMock, mock_open
import logging
import yaml
import pandas as pd
from datetime import datetime
from src.cli.cli_interface import (
    setup_logging,
    load_config,
    check_ib_prerequisites,
    initialize_components,
    process_market_data,
    start_trading_system,
    main
)

class TestCLIInterface(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.config = {
            'risk_management': {
                'position_limits': {
                    'max_position_size': 100
                },
                'loss_limits': {
                    'daily_loss_limit': 1000
                }
            },
            'agent_system': {
                'update_interval': 1
            }
        }
        # Reset logging before each test
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        self.logger = logging.getLogger('test_logger')

    def test_setup_logging(self):
        """Test logging setup"""
        # Reset logging configuration
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        logger = setup_logging()
        self.assertIsInstance(logger, logging.Logger)
        self.assertEqual(logger.level, logging.INFO)
        self.assertTrue(len(logger.handlers) > 0)
        self.assertIsInstance(logger.handlers[0], logging.StreamHandler)
        self.assertTrue(logger.handlers[0].formatter is not None)

    @patch('builtins.open', new_callable=mock_open, read_data="risk_management:\n  position_limits:\n    max_position_size: 100")
    def test_load_config(self, mock_file):
        """Test configuration loading"""
        config = load_config()
        self.assertIsInstance(config, dict)
        self.assertIn('risk_management', config)
        mock_file.assert_called_once_with('src/config/config.yaml', 'r')

    @patch('builtins.open')
    def test_load_config_file_not_found(self, mock_file):
        """Test configuration loading with missing file"""
        mock_file.side_effect = FileNotFoundError()
        with self.assertRaises(FileNotFoundError) as context:
            load_config()
        self.assertIn("Configuration file not found", str(context.exception))

    def test_check_ib_prerequisites(self):
        """Test IB prerequisites check"""
        prerequisites = check_ib_prerequisites()
        self.assertIsInstance(prerequisites, list)
        self.assertEqual(len(prerequisites), 5)
        self.assertTrue(all(isinstance(prereq, str) for prereq in prerequisites))
        self.assertTrue(any("TWS" in prereq for prereq in prerequisites))

    @patch('src.cli.cli_interface.IBClient')
    @patch('src.cli.cli_interface.TradingSwarm')
    def test_initialize_components_success(self, mock_trading_swarm, mock_ib_client):
        """Test successful component initialization"""
        # Configure mocks
        mock_ib_instance = mock_ib_client.return_value
        mock_ib_instance.connect_and_run.return_value = True
        mock_ib_instance.isConnected.return_value = True
        
        mock_swarm_instance = mock_trading_swarm.return_value

        # Test initialization
        ib_client, trading_swarm = initialize_components(self.config, self.logger)
        
        # Verify calls
        mock_ib_client.assert_called_once_with(self.config)
        mock_trading_swarm.assert_called_once_with(self.config)
        mock_ib_instance.connect_and_run.assert_called_once()
        
        # Verify returns
        self.assertEqual(ib_client, mock_ib_instance)
        self.assertEqual(trading_swarm, mock_swarm_instance)

    @patch('src.cli.cli_interface.IBClient')
    def test_initialize_components_connection_failure(self, mock_ib_client):
        """Test component initialization with connection failure"""
        # Configure mock to fail connection
        mock_ib_instance = mock_ib_client.return_value
        mock_ib_instance.connect_and_run.return_value = False

        # Test initialization
        with self.assertRaises(Exception) as context:
            initialize_components(self.config, self.logger)
        
        self.assertIn("Failed to connect to Interactive Brokers", str(context.exception))

    def test_process_market_data_success(self):
        """Test successful market data processing"""
        market_data = {
            'close': [100.0, 101.0, 102.0],
            'high': [101.0, 102.0, 103.0],
            'low': [99.0, 100.0, 101.0],
            'volume': [1000, 1100, 1200],
            'timestamp': ['2024-01-01', '2024-01-02', '2024-01-03']
        }

        result = process_market_data(market_data, 'AAPL', self.logger)
        
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(col in result.columns for col in ['close', 'high', 'low', 'volume']))

    def test_process_market_data_empty(self):
        """Test market data processing with empty data"""
        market_data = {
            'close': [],
            'high': [],
            'low': [],
            'volume': [],
            'timestamp': []
        }

        with self.assertRaises(ValueError) as context:
            process_market_data(market_data, 'AAPL', self.logger)
        
        self.assertIn("Empty market data", str(context.exception))

    def test_process_market_data_missing_close(self):
        """Test market data processing with missing close prices"""
        market_data = {
            'close': None,
            'high': [101.0, 102.0],
            'low': [99.0, 100.0],
            'volume': [1000, 1100]
        }

        with self.assertRaises(ValueError) as context:
            process_market_data(market_data, 'AAPL', self.logger)
        
        self.assertIn("No price data", str(context.exception))

    @patch('src.cli.cli_interface.initialize_components')
    @patch('src.cli.cli_interface.time.sleep', side_effect=KeyboardInterrupt)
    def test_start_trading_system(self, mock_sleep, mock_init_components):
        """Test trading system startup and shutdown"""
        # Configure mocks
        mock_ib_client = MagicMock()
        mock_ib_client.isConnected.return_value = True
        mock_ib_client.get_market_data.return_value = {
            'close': [100.0],
            'high': [101.0],
            'low': [99.0],
            'volume': [1000],
            'timestamp': ['2024-01-01']
        }

        mock_trading_swarm = MagicMock()
        mock_trading_swarm.analyze_trading_opportunity.return_value = {
            'status': 'executed',
            'price': 100.0,
            'size': 10,
            'timestamp': '2024-01-01'
        }

        mock_init_components.return_value = (mock_ib_client, mock_trading_swarm)

        # Test trading system
        start_trading_system(self.config, ['AAPL'], self.logger)

        # Verify calls
        mock_init_components.assert_called_once()
        mock_ib_client.get_market_data.assert_called_with('AAPL')
        mock_trading_swarm.analyze_trading_opportunity.assert_called()
        mock_ib_client.disconnect.assert_called_once()

    @patch('src.cli.cli_interface.setup_logging')
    @patch('src.cli.cli_interface.load_config')
    @patch('src.cli.cli_interface.start_trading_system')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main(self, mock_args, mock_start_trading, mock_load_config, mock_setup_logging):
        """Test main function execution"""
        # Configure mocks
        mock_args.return_value = MagicMock(symbols=['AAPL', 'MSFT'], mode='paper')
        mock_load_config.return_value = self.config
        mock_logger = MagicMock()
        mock_setup_logging.return_value = mock_logger

        # Run main
        main()

        # Verify calls
        mock_setup_logging.assert_called_once()
        mock_load_config.assert_called_once()
        mock_start_trading.assert_called_once_with(self.config, ['AAPL', 'MSFT'], mock_logger)

if __name__ == '__main__':
    unittest.main()
