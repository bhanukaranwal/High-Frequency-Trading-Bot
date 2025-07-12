import importlib
import logging

class StrategyEngine:
    """
    Loads and manages all trading strategies defined in the configuration.
    """
    def __init__(self, event_engine, config):
        self.event_engine = event_engine
        self.config = config
        self.strategies = []
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_strategies()

    def _load_strategies(self):
        """
        Dynamically loads strategy classes based on the configuration.
        """
        for strategy_config in self.config.get('strategies', []):
            if not strategy_config.get('enabled', False):
                continue
            
            try:
                strategy_name = strategy_config['strategy_name']
                module_path = f"src.strategies.{strategy_name.lower()}"
                strategy_module = importlib.import_module(module_path)
                
                StrategyClass = getattr(strategy_module, strategy_name)
                
                instance = StrategyClass(self.event_engine, strategy_config['params'])
                self.strategies.append(instance)
                self.logger.info(f"Successfully loaded strategy '{strategy_name}'")
            except (ImportError, AttributeError) as e:
                self.logger.error(f"Could not load strategy '{strategy_config.get('strategy_name')}': {e}", exc_info=True)

    def register(self):
        """
        Registers all loaded strategies with the event engine.
        Each strategy will have its event handlers (e.g., on_tick) registered.
        """
        for strategy in self.strategies:
            strategy.register_handlers()
            self.logger.info(f"Registered handlers for strategy '{strategy.__class__.__name__}'")
