import unittest
from unittest.mock import patch, MagicMock, call
import threading
import time
from datetime import datetime
from collections import defaultdict
from src.api.ib_connector import IBClient, Contract

class TestIBClient(unittest.TestCase):
    def setUp(self):
        """Initialize test environment"""
        self.config = {
            'api': {
                'tws_endpoint': '127.0.0.1',
                'port': 7497
            }
        }
        self.ib_client = IBClient(self.config)
        self.test_symbol = 'AAPL'
        self.test_req_id = 1

    def test_initialization(self):
        """Test client initialization"""
        self.assertEqual(self.ib_client.host, '127.0.0.1')
        self.assertEqual(self.ib_client.port, 7497)
        self.assertEqual(self.ib_client.client_id, 1)
        self.assertIsInstance(self.ib_client.market_data, defaultdict)
        self.assertIsInstance(self.ib_client.active_requests, dict)
        self.assertIsInstance(self.ib_client._lock, type(threading.Lock()))
        self.assertEqual(self.ib_client.next_req_id, 0)

    @patch.object(IBClient, 'connect')
    @patch.object(threading.Thread, 'start')
    def test_connect_and_run_success(self, mock_thread_start, mock_connect):
        """Test successful connection"""
        # Mock isConnected to return True
        with patch.object(IBClient, 'isConnected', return_value=True):
            result = self.ib_client.connect_and_run()
            
            mock_connect.assert_called_once_with('127.0.0.1', 7497, 1)
            mock_thread_start.assert_called_once()
            self.assertTrue(result)

    @patch.object(IBClient, 'connect')
    def test_connect_and_run_failure(self, mock_connect):
        """Test connection failure"""
        mock_connect.side_effect = Exception("Connection failed")
        result = self.ib_client.connect_and_run()
        self.assertFalse(result)

    def test_error_handling_connection_messages(self):
        """Test handling of connection status messages"""
        with patch('builtins.print') as mock_print:
            self.ib_client.error(1, 2104, "Market data farm connection is OK")
            mock_print.assert_called_with("Connection message: Market data farm connection is OK")

    def test_error_handling_no_security_definition(self):
        """Test handling of no security definition error"""
        self.ib_client.active_requests[1] = 'AAPL'
        with patch('builtins.print') as mock_print:
            self.ib_client.error(1, 200, "No security definition found")
            mock_print.assert_called_with("No security definition found for reqId 1")
            self.assertTrue(self.ib_client.data_received['AAPL'])

    def test_error_handling_market_data_not_subscribed(self):
        """Test handling of market data not subscribed error"""
        self.ib_client.active_requests[1] = 'AAPL'
        with patch('builtins.print') as mock_print:
            self.ib_client.error(1, 354, "Market data not subscribed")
            mock_print.assert_called_with("Market data not subscribed for reqId 1")
            self.assertTrue(self.ib_client.data_received['AAPL'])

    @patch.object(IBClient, 'reqMktData')
    @patch.object(IBClient, 'isConnected', return_value=True)
    def test_get_market_data_request(self, mock_is_connected, mock_req_mkt_data):
        """Test market data request"""
        # Setup mock data
        self.ib_client.data_received[self.test_symbol] = True
        self.ib_client._update_market_data(self.test_symbol, 150.0, 1000)
        
        result = self.ib_client.get_market_data(self.test_symbol)
        
        self.assertIsNotNone(result)
        self.assertIn('close', result)
        self.assertIn('high', result)
        self.assertIn('low', result)
        self.assertIn('volume', result)
        self.assertEqual(result['close'][0], 150.0)
        self.assertEqual(result['volume'][0], 1000)

    @patch.object(IBClient, 'reqMktData')
    @patch.object(IBClient, 'isConnected', return_value=False)
    def test_get_market_data_timeout(self, mock_is_connected, mock_req_mkt_data):
        """Test market data request timeout"""
        # Set data_received to False to simulate timeout
        self.ib_client.data_received[self.test_symbol] = False
        
        # Mock _update_market_data to do nothing
        with patch.object(IBClient, '_update_market_data') as mock_update:
            result = self.ib_client.get_market_data(self.test_symbol)
            self.assertIsNone(result)
            mock_update.assert_not_called()

    def test_get_next_req_id(self):
        """Test request ID generation"""
        initial_id = self.ib_client._get_next_req_id()
        next_id = self.ib_client._get_next_req_id()
        self.assertEqual(next_id, initial_id + 1)

    def test_market_data_type(self):
        """Test handling of market data type changes"""
        self.ib_client.active_requests[self.test_req_id] = self.test_symbol
        with patch('builtins.print') as mock_print:
            self.ib_client.marketDataType(self.test_req_id, 1)
            mock_print.assert_called_with("Receiving real-time market data for AAPL")

    def test_tick_price_last(self):
        """Test handling of last price updates"""
        self.ib_client.active_requests[self.test_req_id] = self.test_symbol
        self.ib_client.tickPrice(self.test_req_id, 4, 150.0, None)  # TICK_LAST
        
        market_data = self.ib_client.market_data[self.test_symbol]
        self.assertEqual(market_data['close'][-1], 150.0)
        self.assertTrue(self.ib_client.data_received[self.test_symbol])

    def test_tick_price_high_low(self):
        """Test handling of high/low price updates"""
        self.ib_client.active_requests[self.test_req_id] = self.test_symbol
        
        # Test high price
        self.ib_client.tickPrice(self.test_req_id, 6, 155.0, None)  # TICK_HIGH
        self.assertEqual(self.ib_client.market_data[self.test_symbol]['current_high'], 155.0)
        
        # Test low price
        self.ib_client.tickPrice(self.test_req_id, 7, 145.0, None)  # TICK_LOW
        self.assertEqual(self.ib_client.market_data[self.test_symbol]['current_low'], 145.0)

    def test_tick_size(self):
        """Test handling of size updates"""
        self.ib_client.active_requests[self.test_req_id] = self.test_symbol
        self.ib_client._update_market_data(self.test_symbol, 150.0, 1000)
        
        self.ib_client.tickSize(self.test_req_id, 8, 2000)  # TICK_VOLUME
        
        market_data = self.ib_client.market_data[self.test_symbol]
        self.assertEqual(market_data['volume'][-1], 2000)
        self.assertTrue(self.ib_client.data_received[self.test_symbol])

    def test_tick_string(self):
        """Test handling of string tick types"""
        self.ib_client.active_requests[self.test_req_id] = self.test_symbol
        
        # Test RT_VOLUME format: price;size;time;total;vwap;single
        self.ib_client.tickString(self.test_req_id, 45, "150.0;1000;1641234567;10000;149.5;1")
        
        market_data = self.ib_client.market_data[self.test_symbol]
        self.assertEqual(market_data['close'][-1], 150.0)
        self.assertEqual(market_data['volume'][-1], 1000)

    def test_update_market_data(self):
        """Test market data updates"""
        symbol = 'AAPL'
        price = 150.0
        size = 1000
        
        self.ib_client._update_market_data(symbol, price, size)
        
        market_data = self.ib_client.market_data[symbol]
        self.assertEqual(market_data['close'][-1], price)
        self.assertEqual(market_data['volume'][-1], size)
        self.assertEqual(market_data['high'][-1], price)
        self.assertEqual(market_data['low'][-1], price)
        self.assertIsInstance(market_data['timestamp'][-1], datetime)

    def test_concurrent_market_data_updates(self):
        """Test thread safety of market data updates"""
        symbol = 'AAPL'
        num_updates = 100
        
        def update_data():
            for i in range(num_updates):
                self.ib_client._update_market_data(symbol, 150.0 + i, 1000 + i)
        
        # Create multiple threads to update data concurrently
        threads = [threading.Thread(target=update_data) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        
        market_data = self.ib_client.market_data[symbol]
        self.assertEqual(len(market_data['close']), num_updates * 5)
        self.assertEqual(len(market_data['volume']), num_updates * 5)
        self.assertEqual(len(market_data['timestamp']), num_updates * 5)

if __name__ == '__main__':
    unittest.main()
