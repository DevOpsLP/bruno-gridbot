import logging
import threading
import ccxt
from websocket_manager.websocket_manager import run_bot_with_websocket
from database import models, crud

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class GridBot:
    def __init__(self):
        self.websocket_connections = {}  # Tracks active WebSocket connections

    def start_symbol(self, exchange: str, symbol: str, db_session):
        """
        Starts the WebSocket for a single symbol on a given exchange.
        Retrieves the trading amount dynamically from the exchange's API key balance.
        """
        exchange = exchange.lower()
        
        # Fetch API key and balance
        key = db_session.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange == exchange).first()
        if not key:
            logger.warning(f"No API key found for {exchange}. Cannot start symbol.")
            return

        amount = key.balance  # ✅ Use balance from API Key model

        # Initialize CCXT connection
        try:
            if exchange == "bitmart":
                exchange_instance = ccxt.bitmart({
                    'apiKey': key.api_key,
                    'secret': key.api_secret,
                    'uid': "bua",
                    'enableRateLimit': True
                })
            else:
                exchange_instance = getattr(ccxt, exchange)()
                exchange_instance.apiKey = key.api_key
                exchange_instance.secret = key.api_secret
                exchange_instance.options["defaultType"] = "spot"
        except Exception as e:
            logger.error(f"Failed to create connection for {exchange}: {str(e)}")
            return

        thread = threading.Thread(
            target=self._start_websocket,
            args=(exchange_instance, symbol, amount, db_session),
            daemon=True
        )
        thread.start()
        logger.info(f"Started WebSocket for {exchange} - {symbol} with amount {amount}")
        
        
    def _start_websocket(self, exchange_instance, symbol, amount, db_session):
        """
        Starts a WebSocket for a specific (exchange, symbol) pair.
        """
        ws = run_bot_with_websocket(exchange_instance, symbol, amount, db_session, self)
        
        # Store the WebSocket reference
        self.websocket_connections[(exchange_instance.id, symbol)] = ws
        logger.info(f"WebSocket launched for {exchange_instance.id} - {symbol}")

    def stop_symbol(self, symbol: str):
        keys_to_stop = [key for key in self.websocket_connections if key[1] == symbol]
        if not keys_to_stop:
            logger.info(f"No active WebSocket for symbol {symbol}.")
            return

        for key in keys_to_stop:
            ws = self.websocket_connections.get(key)
            try:
                logger.info(f"Closing WebSocket for {key}")
                # Turn off reconnect for your library
                if hasattr(ws, "auto_reconnect"):
                    ws.auto_reconnect = False
                if hasattr(ws, "reconnection"):
                    ws.reconnection = False  # Stop internal reconnection

                # Now attempt to close properly
                if hasattr(ws, "exit"):
                    ws.exit()
                elif hasattr(ws, "stop"):
                    ws.stop()
                elif hasattr(ws, "close"):
                    ws.close()
                else:
                    logger.warning("WebSocket has no valid termination method.")

                # Remove it from the dictionary
                del self.websocket_connections[key]

            except Exception as e:
                logger.error(f"Error closing WebSocket for {key}: {e}")

    def stop(self):
        """Stops all WebSocket connections."""
        logger.info("Stopping all WebSocket connections...")
        for key, ws in list(self.websocket_connections.items()):
            try:
                ws.close()
            except Exception as e:
                logger.error(f"Error closing WebSocket for {key}: {e}")
        self.websocket_connections.clear()
        logger.info("All WebSocket connections closed.")

    @property
    def running(self):
        # If there's at least one active WebSocket, we call it 'running'
        return bool(self.websocket_connections)

    def get_symbol_status(self, symbol: str):
        """
        Returns 'running' if the WebSocket for the specified symbol is active,
        otherwise 'stopped'.
        """
        for (exchange, sym), ws in self.websocket_connections.items():
            if sym == symbol:
                # 'ws.sock.connected' is how the python 'websocket-client' tells you it's connected
                return 'running' if ws.sock and ws.sock.connected else 'stopped'
        return 'stopped'

    def get_all_symbols_status(self):
        """
        Returns a dict of symbol -> 'running'/'stopped' for each active WebSocket.
        """
        status = {}
        for (exchange, sym), ws in self.websocket_connections.items():
            status[sym] = 'running' if ws.sock and ws.sock.connected else 'stopped'
        return status
# Global instance for API control
grid_bot = GridBot()