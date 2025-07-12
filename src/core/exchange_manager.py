import importlib
import logging

class ExchangeManager:
    """
    Manages connections to all exchanges defined in the configuration.
    It abstracts away the specifics of each exchange connector.
    """
    def __init__(self, event_engine, config):
        self.event_engine = event_engine
        self.config = config
        self.exchanges = {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_exchanges()

    def _load_exchanges(self):
        """
        Dynamically loads exchange connectors based on the configuration file.
        """
        for name, ex_config in self.config['exchanges'].items():
            try:
                connector_name = ex_config['connector']
                module_path = f"src.connectors.{connector_name}_connector"
                connector_module = importlib.import_module(module_path)
                
                # Assumes the connector class is named like 'BinanceConnector'
                class_name = f"{connector_name.capitalize()}Connector"
                ConnectorClass = getattr(connector_module, class_name)
                
                self.exchanges[name] = ConnectorClass(name, ex_config, self.event_engine)
                self.logger.info(f"Successfully loaded connector for '{name}'")
            except (ImportError, AttributeError) as e:
                self.logger.error(f"Could not load connector for '{name}': {e}", exc_info=True)

    async def connect_all(self):
        """
        Connects to all loaded exchanges.
        """
        for name, exchange in self.exchanges.items():
            try:
                await exchange.connect()
                self.logger.info(f"Connection initiated for {name}.")
            except Exception as e:
                self.logger.error(f"Failed to connect to {name}: {e}", exc_info=True)
    
    async def disconnect_all(self):
        """
        Disconnects from all exchanges gracefully.
        """
        for name, exchange in self.exchanges.items():
            try:
                await exchange.disconnect()
                self.logger.info(f"Disconnected from {name}.")
            except Exception as e:
                self.logger.error(f"Error disconnecting from {name}: {e}", exc_info=True)

    def get_exchange(self, name):
        """
        Returns an instance of a specific exchange connector.
        """
        return self.exchanges.get(name)

