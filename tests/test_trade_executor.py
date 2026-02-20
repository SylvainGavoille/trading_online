import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, UTC
from src.trading.agents.trade_executor import TradeExecutor, OrderState
from src.api.ib_connector import IBClient

class TestTradeExecutor(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.mock_api_connector = MagicMock(spec=IBClient)
        self.trade_executor = TradeExecutor(self.mock_api_connector)
        
        # Sample trade parameters
        self.trade_params = {
            'symbol': 'AAPL',
            'size': 100,
            'price': 150.00,
            'stop_loss': 148.50,
            'target_price': 155.00
        }

    def test_execute_trade_success(self):
        """Test successful trade execution with all orders"""
        # Setup mock responses
        self.mock_api_connector.placeOrder.side_effect = [
            {'order_id': '1', 'status': 'filled', 'filled_price': 150.00},  # Main order
            {'order_id': '2', 'status': 'pending'},  # Stop loss order
            {'order_id': '3', 'status': 'pending'}   # Take profit order
        ]
        
        # Execute trade
        result = self.trade_executor.execute_trade(self.trade_params)
        
        # Verify result
        self.assertEqual(result['status'], 'executed')
        self.assertIn('orders', result)
        self.assertEqual(len(result['orders']), 3)
        
        # Verify order states were created
        self.assertEqual(len(self.trade_executor.orders), 3)
        self.assertEqual(len(self.trade_executor.symbol_orders['AAPL']), 3)
        
        # Verify order relationships
        main_order = self.trade_executor.get_order_state('1')
        self.assertIsNotNone(main_order)
        self.assertEqual(len(main_order.child_order_ids), 2)
        self.assertIsNone(main_order.parent_order_id)
        
        stop_order = self.trade_executor.get_order_state('2')
        self.assertIsNotNone(stop_order)
        self.assertEqual(stop_order.parent_order_id, '1')
        
        target_order = self.trade_executor.get_order_state('3')
        self.assertIsNotNone(target_order)
        self.assertEqual(target_order.parent_order_id, '1')

    def test_execute_trade_main_order_failure(self):
        """Test trade execution with main order failure"""
        # Setup mock to return None for main order
        self.mock_api_connector.placeOrder.return_value = None
        
        # Execute trade
        result = self.trade_executor.execute_trade(self.trade_params)
        
        # Verify result
        self.assertEqual(result['status'], 'error')
        self.assertEqual(len(self.trade_executor.orders), 0)
        self.assertEqual(len(self.trade_executor.symbol_orders['AAPL']), 0)

    def test_execute_trade_stop_loss_failure(self):
        """Test trade execution with stop loss order failure"""
        # Setup mock responses
        self.mock_api_connector.placeOrder.side_effect = [
            {'order_id': '1', 'status': 'filled', 'filled_price': 150.00},  # Main order
            None,  # Stop loss order fails
        ]
        self.mock_api_connector.cancelOrder.return_value = True
        
        # Execute trade
        result = self.trade_executor.execute_trade(self.trade_params)
        
        # Verify result
        self.assertEqual(result['status'], 'error')
        
        # Verify main order was canceled
        self.mock_api_connector.cancelOrder.assert_called_once_with('1')
        
        # Verify order states
        main_order = self.trade_executor.get_order_state('1')
        self.assertIsNotNone(main_order)
        self.assertEqual(main_order.status, 'canceled')

    def test_execute_trade_take_profit_failure(self):
        """Test trade execution with take profit order failure"""
        # Setup mock responses
        self.mock_api_connector.placeOrder.side_effect = [
            {'order_id': '1', 'status': 'filled', 'filled_price': 150.00},  # Main order
            {'order_id': '2', 'status': 'pending'},  # Stop loss order
            None  # Take profit order fails
        ]
        self.mock_api_connector.cancelOrder.return_value = True
        
        # Execute trade
        result = self.trade_executor.execute_trade(self.trade_params)
        
        # Verify result
        self.assertEqual(result['status'], 'error')
        
        # Verify both orders were canceled
        self.mock_api_connector.cancelOrder.assert_any_call('1')
        self.mock_api_connector.cancelOrder.assert_any_call('2')
        
        # Verify order states
        for order_id in ['1', '2']:
            order = self.trade_executor.get_order_state(order_id)
            self.assertIsNotNone(order)
            self.assertEqual(order.status, 'canceled')

    def test_order_state_tracking(self):
        """Test order state tracking functionality"""
        # Create order state
        order_state = OrderState('1', 'AAPL', 'market', 100, 150.00)
        
        # Verify initial state
        self.assertEqual(order_state.order_id, '1')
        self.assertEqual(order_state.symbol, 'AAPL')
        self.assertEqual(order_state.order_type, 'market')
        self.assertEqual(order_state.quantity, 100)
        self.assertEqual(order_state.price, 150.00)
        self.assertEqual(order_state.status, 'pending')
        self.assertEqual(order_state.filled_quantity, 0)
        self.assertIsNone(order_state.filled_price)
        self.assertIsNone(order_state.parent_order_id)
        self.assertEqual(len(order_state.child_order_ids), 0)

    def test_get_symbol_orders(self):
        """Test retrieving orders for a symbol"""
        # Setup some orders
        self.mock_api_connector.placeOrder.side_effect = [
            {'order_id': '1', 'status': 'filled', 'filled_price': 150.00},
            {'order_id': '2', 'status': 'pending'},
            {'order_id': '3', 'status': 'pending'}
        ]
        
        # Execute trade
        self.trade_executor.execute_trade(self.trade_params)
        
        # Get orders for symbol
        orders = self.trade_executor.get_symbol_orders('AAPL')
        
        # Verify
        self.assertEqual(len(orders), 3)
        self.assertTrue(all(order.symbol == 'AAPL' for order in orders))

    def test_cancel_order(self):
        """Test order cancellation"""
        # Setup order
        self.mock_api_connector.placeOrder.return_value = {
            'order_id': '1', 'status': 'pending'
        }
        self.mock_api_connector.cancelOrder.return_value = True
        
        # Place order
        self.trade_executor.execute_trade(self.trade_params)
        
        # Cancel order
        result = self.trade_executor._cancel_order('1')
        
        # Verify
        self.assertTrue(result)
        order_state = self.trade_executor.get_order_state('1')
        self.assertEqual(order_state.status, 'canceled')

    def test_get_portfolio(self):
        """Test portfolio retrieval"""
        # Setup mock
        portfolio_data = {'total_value': 100000, 'daily_loss': 500}
        self.mock_api_connector.getPortfolio.return_value = portfolio_data
        
        # Get portfolio
        result = self.trade_executor.get_portfolio()
        
        # Verify
        self.assertEqual(result, portfolio_data)

    def test_get_daily_trades(self):
        """Test daily trades retrieval"""
        # Setup mock
        trades_data = [
            {'symbol': 'AAPL', 'quantity': 100, 'price': 150.00},
            {'symbol': 'AAPL', 'quantity': -50, 'price': 152.00}
        ]
        self.mock_api_connector.getDailyTrades.return_value = trades_data
        
        # Get daily trades
        result = self.trade_executor.get_daily_trades('AAPL')
        
        # Verify
        self.assertEqual(result, trades_data)

if __name__ == '__main__':
    unittest.main()
