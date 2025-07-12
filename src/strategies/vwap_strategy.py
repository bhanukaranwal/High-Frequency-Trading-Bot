import logging
import pandas as pd
from datetime import datetime, time

from src.core.event_engine import Event

class VWAPStrategy:
    """
    A strategy that attempts to execute a large order by placing smaller orders
    at or better than the Volume-Weighted Average Price (VWAP).
    """
    def __init__(self, event_engine, params):
        self.event_engine = event_engine
        self.params = params
        self.logger = logging.getLogger(self.__class__.__name__)

        # Strategy parameters
        self.exchange = params['exchange']
        self.symbol = params['symbol']
        self.vwap_period = pd.to_timedelta(params['vwap_period'], unit='m')
        self.order_amount = params['order_amount']
        self.target_spread_pct = params['target_spread_pct']
        self.start_time = datetime.strptime(params['start_time'], '%H:%M').time()
        self.end_time = datetime.strptime(params['end_time'], '%H:%M').time()

        # State variables
        self.historical_data = pd.DataFrame(columns=['price', 'quantity'])
        self.vwap = None
        self.is_active = False

    def register_handlers(self):
        """
        Registers the event handlers for this strategy.
        """
        self.event_engine.register_handler('TICK', self.on_tick)
        # Could also register a handler for time-based events if needed
        # self.event_engine.register_handler('TIME_UPDATE', self.check_time)

    async def on_tick(self, event: Event):
        """
        Handles incoming tick data.
        """
        if event.data['exchange'] != self.exchange or event.data['symbol'] != self.symbol:
            return

        # Check if strategy should be active
        if not self._is_within_trading_window():
            if self.is_active:
                self.logger.info("Exiting trading window. VWAP strategy is now inactive.")
                self.is_active = False
            return
        
        if not self.is_active:
            self.logger.info("Entering trading window. VWAP strategy is now active.")
            self.is_active = True

        # Update historical data and calculate VWAP
        tick_data = event.data
        timestamp = pd.to_datetime(tick_data['timestamp'], unit='ms')
        
        # Using pandas DataFrame for easier manipulation
        new_row = pd.DataFrame([{'price': tick_data['price'], 'quantity': tick_data['quantity']}], index=[timestamp])
        self.historical_data = pd.concat([self.historical_data, new_row])

        # Trim data to the VWAP period
        self.historical_data = self.historical_data.last(self.vwap_period)

        self._calculate_vwap()

        # Make trading decision
        if self.vwap is not None:
            await self._make_decision(tick_data['price'])

    def _calculate_vwap(self):
        """
        Calculates the VWAP from the stored historical data.
        """
        if self.historical_data.empty:
            return

        df = self.historical_data
        df['pv'] = df['price'] * df['quantity']
        self.vwap = df['pv'].sum() / df['quantity'].sum()
        self.logger.debug(f"Calculated VWAP for {self.symbol}: {self.vwap:.2f}")

    async def _make_decision(self, current_price):
        """
        Decides whether to place a buy or sell order based on the VWAP.
        This is a simplified logic for demonstration.
        """
        # Example: Buy if the price is below VWAP by a certain percentage
        target_buy_price = self.vwap * (1 - self.target_spread_pct)
        if current_price < target_buy_price:
            self.logger.info(f"Price {current_price:.2f} is below target buy price {target_buy_price:.2f}. Placing BUY order.")
            
            order_data = {
                'strategy_id': self.__class__.__name__,
                'exchange': self.exchange,
                'symbol': self.symbol,
                'side': 'BUY',
                'type': 'LIMIT',
                'quantity': self.order_amount,
                'price': current_price, # Place at current market price for aggression
            }
            await self.event_engine.push_event(Event('SIGNAL', order_data))

        # Example: Sell if the price is above VWAP (for a sell program)
        # target_sell_price = self.vwap * (1 + self.target_spread_pct)
        # if current_price > target_sell_price:
        #     ...

    def _is_within_trading_window(self):
        """
        Checks if the current time is within the strategy's active window.
        """
        now_utc = datetime.utcnow().time()
        return self.start_time <= now_utc <= self.end_time

