import asyncio
from collections import defaultdict
import logging

class Event:
    """
    Base class for all events.
    """
    def __init__(self, event_type, data=None):
        self.type = event_type
        self.data = data if data is not None else {}

    def __str__(self):
        return f"Event(type={self.type}, data={self.data})"

class EventEngine:
    """
    Manages the event queue and dispatches events to registered handlers.
    This is the central nervous system of the trading bot.
    """
    def __init__(self):
        self._queue = asyncio.Queue()
        self._handlers = defaultdict(list)
        self._running = False
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_handler(self, event_type, handler):
        """
        Register a handler for a specific event type.
        A handler is an async function that accepts an event.
        """
        self._handlers[event_type].append(handler)
        self.logger.debug(f"Handler {handler.__name__} registered for event type '{event_type}'")

    async def push_event(self, event):
        """
        Push a new event onto the queue.
        """
        await self._queue.put(event)

    async def _run(self):
        """
        The main event loop. It continuously fetches events from the queue
        and dispatches them to the appropriate handlers.
        """
        self.logger.info("Event engine loop started.")
        while self._running:
            try:
                event = await self._queue.get()
                self.logger.debug(f"Processing event: {event}")
                if event.type in self._handlers:
                    for handler in self._handlers[event.type]:
                        # Schedule handler to run concurrently
                        asyncio.create_task(handler(event))
            except Exception as e:
                self.logger.error(f"Error in event loop: {e}", exc_info=True)

    async def start(self):
        """
        Starts the event engine's main loop.
        """
        if not self._running:
            self._running = True
            await self._run()

    def stop(self):
        """
        Stops the event engine.
        """
        self._running = False
        self.logger.info("Event engine stopping.")

