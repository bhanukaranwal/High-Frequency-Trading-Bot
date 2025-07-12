import asyncio
import yaml
import logging
from logging.config import dictConfig

from src.core.event_engine import EventEngine
from src.core.exchange_manager import ExchangeManager
from src.core.strategy_engine import StrategyEngine
from src.core.order_manager import OrderManager
from src.core.risk_manager import RiskManager
from src.data.data_handler import DataHandler
from src.analytics.performance import PerformanceMonitor

def setup_logging(config):
    """Sets up logging configuration."""
    try:
        dictConfig(config['logging'])
        logging.info("Logging configured successfully.")
    except Exception as e:
        logging.basicConfig(level=logging.INFO)
        logging.warning(f"Could not configure logging from file: {e}. Using basic config.")

async def main(config_path: str):
    """
    Main function to initialize and run the trading bot.
    """
    # Load Configuration
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_path}")
        return
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file: {e}")
        return

    # Setup Logging
    setup_logging(config)
    
    logging.info("Initializing High-Frequency Trading Bot...")

    # 1. Initialize Core Components
    event_engine = EventEngine()
    
    # 2. Initialize Managers and Engines
    exchange_manager = ExchangeManager(event_engine, config)
    data_handler = DataHandler(event_engine, exchange_manager)
    strategy_engine = StrategyEngine(event_engine, config)
    order_manager = OrderManager(event_engine, exchange_manager)
    risk_manager = RiskManager(event_engine, config)
    performance_monitor = PerformanceMonitor(event_engine, config)

    # Register components to the event engine (order matters for some dependencies)
    # The order of registration can be important. For example, risk manager should see orders before the order manager processes them.
    risk_manager.register()
    order_manager.register()
    strategy_engine.register()
    data_handler.register()
    performance_monitor.register()


    # 3. Start the Event Engine
    # This starts the main event loop in the background.
    event_engine_task = asyncio.create_task(event_engine.start())
    logging.info("Event Engine started.")

    # 4. Connect to Exchanges
    # This will trigger the data streams to start.
    await exchange_manager.connect_all()
    logging.info("Exchange connections initiated.")

    # 5. Run indefinitely
    # The main logic is now running in the background via the event engine.
    # We can add a graceful shutdown mechanism here.
    try:
        await event_engine_task
    except asyncio.CancelledError:
        logging.info("Main task cancelled. Shutting down.")
    finally:
        logging.info("Shutting down bot...")
        await exchange_manager.disconnect_all()
        event_engine.stop()
        logging.info("Bot has been shut down.")


if __name__ == "__main__":
    # In a real application, you might use command-line arguments to specify the config file.
    config_file = 'config.yaml'
    try:
        asyncio.run(main(config_file))
    except KeyboardInterrupt:
        logging.info("Application interrupted by user. Exiting.")

