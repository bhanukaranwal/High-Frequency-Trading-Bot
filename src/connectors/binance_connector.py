import asyncio
import aiohttp
import json
import logging
import hmac
import hashlib
import time

from src.core.event_engine import Event

class BinanceConnector:
    """
    Connector for Binance (Futures in this example).
    Handles WebSocket connections for market data and REST API for orders.
    """
    def __init__(self, name, config, event_engine):
        self.name = name
        self.config = config
        self.event_engine = event_engine
        self.logger = logging.getLogger(f"BinanceConnector.{self.name}")
        self.ws = None
        self.session = None

    async def connect(self):
        """
        Establishes a WebSocket connection for market data streams.
        """
        self.session = aiohttp.ClientSession()
        # Subscribe to streams defined in strategies
        streams = self._get_streams_from_strategies()
        if not streams:
            self.logger.warning("No streams to subscribe to for Binance.")
            return

        url = f"{self.config['ws_url']}/{'/'.join(streams)}"
        self.logger.info(f"Connecting to Binance WebSocket: {url}")
        
        try:
            self.ws = await self.session.ws_connect(url)
            asyncio.create_task(self._listen())
        except Exception as e:
            self.logger.error(f"Binance WebSocket connection failed: {e}", exc_info=True)

    def _get_streams_from_strategies(self):
        """
        Gathers required WebSocket streams from the strategy configurations.
        """
        streams = set()
        for strategy_config in self.config.get('strategies', []):
            if strategy_config.get('params', {}).get('exchange') == self.name:
                symbol = strategy_config['params']['symbol'].lower()
                # Example streams, can be expanded
                streams.add(f"{symbol}@trade") # For tick data
                streams.add(f"{symbol}@depth5@100ms") # For order book data
        return list(streams)

    async def _listen(self):
        """
        Listens for messages from the WebSocket and pushes them to the event engine.
        """
        self.logger.info("Listening for Binance WebSocket messages...")
        while True:
            try:
                msg = await self.ws.receive()
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._handle_message(data)
                elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    self.logger.warning("Binance WebSocket connection closed or errored. Reconnecting...")
                    await self._reconnect()
                    break
            except Exception as e:
                self.logger.error(f"Error in Binance listener: {e}", exc_info=True)
                await self._reconnect()
                break

    async def _reconnect(self):
        """Handles reconnection logic."""
        await self.disconnect()
        await asyncio.sleep(5) # Wait before reconnecting
        await self.connect()

    async def _handle_message(self, data):
        """
        Parses WebSocket messages and creates corresponding events.
        """
        stream = data.get('stream')
        if not stream:
            return

        payload = data.get('data', {})
        
        if '@trade' in stream:
            event_data = {
                'exchange': self.name,
                'symbol': payload['s'],
                'price': float(payload['p']),
                'quantity': float(payload['q']),
                'timestamp': payload['T']
            }
            await self.event_engine.push_event(Event('TICK', event_data))
        
        elif '@depth' in stream:
            event_data = {
                'exchange': self.name,
                'symbol': stream.split('@')[0].upper(),
                'bids': [(float(p), float(q)) for p, q in payload['b']],
                'asks': [(float(p), float(q)) for p, q in payload['a']],
                'timestamp': payload.get('E')
            }
            await self.event_engine.push_event(Event('ORDER_BOOK_UPDATE', event_data))


    async def place_order(self, order_data):
        """
        Places an order via the REST API.
        """
        # This is a simplified example. A real implementation would be more robust.
        endpoint = "/fapi/v1/order"
        params = {
            'symbol': order_data['symbol'],
            'side': order_data['side'].upper(),
            'type': order_data['type'].upper(),
            'quantity': order_data['quantity'],
            'timestamp': int(time.time() * 1000),
        }
        if order_data['type'].lower() == 'limit':
            params['price'] = order_data['price']
            params['timeInForce'] = 'GTC'

        signature = self._generate_signature(params)
        params['signature'] = signature
        
        headers = {'X-MBX-APIKEY': self.config['api_key']}
        url = f"{self.config['base_url']}{endpoint}"

        try:
            async with self.session.post(url, headers=headers, params=params) as response:
                response_data = await response.json()
                if response.status == 200:
                    self.logger.info(f"Order placed successfully: {response_data}")
                    # Push an ORDER_STATUS event
                    await self.event_engine.push_event(Event('ORDER_STATUS', response_data))
                else:
                    self.logger.error(f"Failed to place order: {response_data}")
                    # Push an ORDER_FAILED event
                    await self.event_engine.push_event(Event('ORDER_FAILED', {'order': order_data, 'response': response_data}))

        except Exception as e:
            self.logger.error(f"Error placing order: {e}", exc_info=True)

    def _generate_signature(self, params):
        """Generates the HMAC SHA256 signature for API requests."""
        query_string = '&'.join([f"{key}={value}" for key, value in params.items()])
        return hmac.new(self.config['api_secret'].encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()


    async def disconnect(self):
        """
        Closes the WebSocket and HTTP session.
        """
        if self.ws and not self.ws.closed:
            await self.ws.close()
            self.logger.info("Binance WebSocket closed.")
        if self.session and not self.session.closed:
            await self.session.close()
            self.logger.info("AIOHTTP session closed.")

