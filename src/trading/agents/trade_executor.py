import logging
from typing import Dict, Any, Optional
from datetime import datetime, UTC
from collections import defaultdict
from src.api.ib_connector import IBClient

class OrderState:
    """Tracks the state of an order"""
    def __init__(self, order_id: str, symbol: str, order_type: str, quantity: int, price: Optional[float] = None):
        self.order_id = order_id
        self.symbol = symbol
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.status = "pending"
        self.filled_quantity = 0
        self.filled_price = None
        self.created_at = datetime.now(UTC)
        self.updated_at = self.created_at
        self.parent_order_id = None
        self.child_order_ids = []

class TradeExecutor:
    """Handles trade execution and order management"""
    
    def __init__(self, api_connector: IBClient):
        """
        Initialize trade executor
        
        Args:
            api_connector: API connector for trade execution
        """
        self.api_connector = api_connector
        self.logger = logging.getLogger(__name__)
        self.orders = {}  # Order ID to OrderState mapping
        self.symbol_orders = defaultdict(list)  # Symbol to Order IDs mapping
    
    def execute_trade(self, trade_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade based on validated parameters
        
        Args:
            trade_params: Dictionary containing trade parameters
                Required keys:
                - symbol: Trading symbol
                - size: Position size
                - price: Current price
                - stop_loss: Stop loss price
                - target_price: Target price
                
        Returns:
            Dictionary containing execution results
        """
        try:
            self.logger.info(f"Executing trade for {trade_params['symbol']}")
            
            # Validate required parameters
            required_params = ['symbol', 'size', 'price', 'stop_loss', 'target_price']
            if not all(param in trade_params for param in required_params):
                self.logger.error("Missing required trade parameters")
                return {
                    'status': 'error',
                    'reason': 'Missing required trade parameters'
                }
            
            # Place main order
            main_order = self._place_main_order(trade_params)
            if not main_order:
                self.logger.error("Failed to place main order")
                return {
                    'status': 'error',
                    'reason': 'Failed to place main order'
                }
            
            # Place stop loss order
            stop_order = self._place_stop_loss_order(trade_params, main_order['order_id'])
            if not stop_order:
                self.logger.error("Failed to place stop loss order")
                self._cancel_order(main_order['order_id'])
                return {
                    'status': 'error',
                    'reason': 'Failed to place stop loss order'
                }
            
            # Place take profit order
            target_order = self._place_take_profit_order(trade_params, main_order['order_id'])
            if not target_order:
                self.logger.error("Failed to place take profit order")
                self._cancel_order(main_order['order_id'])
                self._cancel_order(stop_order['order_id'])
                return {
                    'status': 'error',
                    'reason': 'Failed to place take profit order'
                }
            
            # Update order relationships
            self._link_orders(main_order['order_id'], [stop_order['order_id'], target_order['order_id']])
            
            execution_result = {
                'status': 'executed',
                'timestamp': datetime.now(UTC).isoformat(),
                'orders': {
                    'main': main_order,
                    'stop_loss': stop_order,
                    'take_profit': target_order
                },
                'trade_params': trade_params
            }
            
            self.logger.info(f"Trade executed successfully: {execution_result}")
            return execution_result
            
        except Exception as e:
            self.logger.exception(f"Trade execution error: {str(e)}")
            return {
                'status': 'error',
                'reason': f'Trade execution error: {str(e)}'
            }
    
    def _place_main_order(self, trade_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place the main market order"""
        try:
            self.logger.info(f"Placing main order for {trade_params['symbol']}")
            
            order = self.api_connector.placeOrder(
                symbol=trade_params['symbol'],
                order_type='market',
                quantity=trade_params['size']
            )
            
            if order:
                # Create and store order state
                order_state = OrderState(
                    order_id=order['order_id'],
                    symbol=trade_params['symbol'],
                    order_type='market',
                    quantity=trade_params['size']
                )
                self._store_order_state(order_state)
                
                return {
                    'order_id': order['order_id'],
                    'status': order['status'],
                    'filled_price': order.get('filled_price', trade_params['price'])
                }
                
            return None
            
        except Exception as e:
            self.logger.exception(f"Error placing main order: {str(e)}")
            return None
    
    def _place_stop_loss_order(self, trade_params: Dict[str, Any], 
                             parent_order_id: str) -> Optional[Dict[str, Any]]:
        """Place stop loss order"""
        try:
            self.logger.info(f"Placing stop loss order for {trade_params['symbol']}")
            
            order = self.api_connector.placeOrder(
                symbol=trade_params['symbol'],
                order_type='stop',
                quantity=trade_params['size'],
                price=trade_params['stop_loss'],
                parent_order_id=parent_order_id
            )
            
            if order:
                # Create and store order state
                order_state = OrderState(
                    order_id=order['order_id'],
                    symbol=trade_params['symbol'],
                    order_type='stop',
                    quantity=trade_params['size'],
                    price=trade_params['stop_loss']
                )
                order_state.parent_order_id = parent_order_id
                self._store_order_state(order_state)
                
                return {
                    'order_id': order['order_id'],
                    'status': order['status'],
                    'stop_price': trade_params['stop_loss']
                }
                
            return None
            
        except Exception as e:
            self.logger.exception(f"Error placing stop loss order: {str(e)}")
            return None
    
    def _place_take_profit_order(self, trade_params: Dict[str, Any], 
                               parent_order_id: str) -> Optional[Dict[str, Any]]:
        """Place take profit order"""
        try:
            self.logger.info(f"Placing take profit order for {trade_params['symbol']}")
            
            order = self.api_connector.placeOrder(
                symbol=trade_params['symbol'],
                order_type='limit',
                quantity=trade_params['size'],
                price=trade_params['target_price'],
                parent_order_id=parent_order_id
            )
            
            if order:
                # Create and store order state
                order_state = OrderState(
                    order_id=order['order_id'],
                    symbol=trade_params['symbol'],
                    order_type='limit',
                    quantity=trade_params['size'],
                    price=trade_params['target_price']
                )
                order_state.parent_order_id = parent_order_id
                self._store_order_state(order_state)
                
                return {
                    'order_id': order['order_id'],
                    'status': order['status'],
                    'target_price': trade_params['target_price']
                }
                
            return None
            
        except Exception as e:
            self.logger.exception(f"Error placing take profit order: {str(e)}")
            return None
    
    def _cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        try:
            self.logger.info(f"Canceling order {order_id}")
            
            result = bool(self.api_connector.cancelOrder(order_id))
            if result:
                if order_id in self.orders:
                    self.orders[order_id].status = "canceled"
                    self.orders[order_id].updated_at = datetime.now(UTC)
            return result
            
        except Exception as e:
            self.logger.exception(f"Error canceling order {order_id}: {str(e)}")
            return False
    
    def _store_order_state(self, order_state: OrderState) -> None:
        """Store order state and update indices"""
        self.orders[order_state.order_id] = order_state
        self.symbol_orders[order_state.symbol].append(order_state.order_id)
    
    def _link_orders(self, parent_id: str, child_ids: list) -> None:
        """Link parent and child orders"""
        if parent_id in self.orders:
            parent_order = self.orders[parent_id]
            parent_order.child_order_ids.extend(child_ids)
            
            for child_id in child_ids:
                if child_id in self.orders:
                    self.orders[child_id].parent_order_id = parent_id
    
    def get_order_state(self, order_id: str) -> Optional[OrderState]:
        """Get the current state of an order"""
        return self.orders.get(order_id)
    
    def get_symbol_orders(self, symbol: str) -> list:
        """Get all orders for a symbol"""
        return [
            self.orders[order_id]
            for order_id in self.symbol_orders[symbol]
            if order_id in self.orders
        ]
    
    def get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio state"""
        try:
            return self.api_connector.getPortfolio() or {}
        except Exception as e:
            self.logger.exception(f"Error getting portfolio: {str(e)}")
            return {}
    
    def get_daily_trades(self, symbol: str) -> list:
        """Get trades made today for a symbol"""
        try:
            return self.api_connector.getDailyTrades(symbol) or []
        except Exception as e:
            self.logger.exception(f"Error getting daily trades: {str(e)}")
            return []
