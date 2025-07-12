import logging
import uuid

from src.core.event_engine import Event

class OrderManager:
    """
    Handles the lifecycle of orders: creation, sending to exchange, tracking status.
    """
    def __init__(self, event_engine, exchange_manager):
        self.event_engine = event_engine
        self.exchange_manager = exchange_manager
        self.logger = logging.getLogger(self.__class__.__name__)
        self.active_orders = {}

    def register(self):
        """Registers event handlers for the OrderManager."""
        self.event_engine.register_handler('SIGNAL', self.on_signal)
        self.event_engine.register_handler('ORDER_STATUS', self.on_order_status)

    async def on_signal(self, event: Event):
        """
        Receives a signal event from a strategy and creates an order.
        """
        signal_data = event.data
        self.logger.info(f"Received signal to {signal_data['side']} {signal_data['quantity']} {signal_data['symbol']} at {signal_data.get('price')}")
        
        # The risk manager will intercept this event first.
        # If it passes, it will be re-emitted as a confirmed order event.
        # For simplicity here, we'll just create the order directly.
        # In a full implementation, we would listen for an 'ORDER_REQUEST_CONFIRMED' event.
        
        order_event = Event('ORDER_CREATE', signal_data)
        await self.event_engine.push_event(order_event)
        
        # Let's assume the risk manager is synchronous for now, or we listen for a confirmation.
        # For this example, we proceed to place the order.
        await self.place_order(signal_data)


    async def place_order(self, order_data):
        """
        Sends the order to the specified exchange.
        """
        order_id = str(uuid.uuid4())
        order_data['client_order_id'] = order_id
        self.active_orders[order_id] = order_data

        exchange_name = order_data['exchange']
        exchange = self.exchange_manager.get_exchange(exchange_name)

        if not exchange:
            self.logger.error(f"Cannot place order. Exchange '{exchange_name}' not found.")
            return

        await exchange.place_order(order_data)
        self.logger.info(f"Order {order_id} sent to {exchange_name}.")


    async def on_order_status(self, event: Event):
        """
        Handles updates on order status from the exchange.
        """
        status_data = event.data
        client_order_id = status_data.get('c') # clientOrderId from Binance
        
        if client_order_id in self.active_orders:
            self.logger.info(f"Received status update for order {client_order_id}: {status_data['X']}")
            
            if status_data['X'] == 'FILLED' or status_data['X'] == 'PARTIALLY_FILLED':
                fill_event = Event('FILL', {
                    'exchange': self.active_orders[client_order_id]['exchange'],
                    'symbol': status_data['s'],
                    'client_order_id': client_order_id,
                    'exchange_order_id': status_data['i'],
                    'side': status_data['S'],
                    'price': float(status_data['L']),
                    'quantity': float(status_data['l']),
                    'timestamp': status_data['T']
                })
                await self.event_engine.push_event(fill_event)

            if status_data['X'] in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
                del self.active_orders[client_order_id]
                self.logger.info(f"Order {client_order_id} is now closed.")

