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

    def stop_symbol(self, symbol: str, exchange: str = None):
        """
        Stops the WebSocket for a symbol on a specific exchange or all exchanges.
        Args:
            symbol: The trading pair symbol
            exchange: Optional exchange name. If provided, only stops the symbol on that exchange.
        """
        if exchange:
            # Stop specific exchange
            key = (exchange.lower(), symbol)
            ws = self.websocket_connections.get(key)
            if ws:
                try:
                    logger.info(f"Closing WebSocket for {key}")
                    # Disable all possible reconnection mechanisms BEFORE closing
                    if hasattr(ws, "auto_reconnect"):
                        ws.auto_reconnect = False
                    if hasattr(ws, "reconnection"):
                        ws.reconnection = False
                    if hasattr(ws, "keep_running"):
                        ws.keep_running = False
                    if hasattr(ws, "ping_interval"):
                        ws.ping_interval = None
                    if hasattr(ws, "ping_timeout"):
                        ws.ping_timeout = None
                    if hasattr(ws, "reconnect"):
                        ws.reconnect = False
                    if hasattr(ws, "should_reconnect"):
                        ws.should_reconnect = False
                    if hasattr(ws, "max_reconnect_attempts"):
                        ws.max_reconnect_attempts = 0

                    # Force close the connection
                    if hasattr(ws, "sock") and ws.sock is not None:
                        try:
                            ws.sock.close()
                        except Exception as e:
                            logger.error(f"Error closing socket: {e}")

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
                    logger.info(f"Successfully stopped WebSocket for {key}")

                except Exception as e:
                    logger.error(f"Error closing WebSocket for {key}: {e}")
                    # Even if there's an error, remove it from the dictionary
                    if key in self.websocket_connections:
                        del self.websocket_connections[key]
            else:
                logger.info(f"No active WebSocket for {symbol} on {exchange}")
        else:
            # Stop all exchanges (original behavior)
            keys_to_stop = [key for key in self.websocket_connections if key[1] == symbol]
            if not keys_to_stop:
                logger.info(f"No active WebSocket for symbol {symbol}.")
                return

            for key in keys_to_stop:
                ws = self.websocket_connections.get(key)
                try:
                    logger.info(f"Closing WebSocket for {key}")
                    # Disable all possible reconnection mechanisms BEFORE closing
                    if hasattr(ws, "auto_reconnect"):
                        ws.auto_reconnect = False
                    if hasattr(ws, "reconnection"):
                        ws.reconnection = False
                    if hasattr(ws, "keep_running"):
                        ws.keep_running = False
                    if hasattr(ws, "ping_interval"):
                        ws.ping_interval = None
                    if hasattr(ws, "ping_timeout"):
                        ws.ping_timeout = None
                    if hasattr(ws, "reconnect"):
                        ws.reconnect = False
                    if hasattr(ws, "should_reconnect"):
                        ws.should_reconnect = False
                    if hasattr(ws, "max_reconnect_attempts"):
                        ws.max_reconnect_attempts = 0

                    # Force close the connection
                    if hasattr(ws, "sock") and ws.sock is not None:
                        try:
                            ws.sock.close()
                        except Exception as e:
                            logger.error(f"Error closing socket: {e}")

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
                    logger.info(f"Successfully stopped WebSocket for {key}")

                except Exception as e:
                    logger.error(f"Error closing WebSocket for {key}: {e}")
                    # Even if there's an error, remove it from the dictionary
                    if key in self.websocket_connections:
                        del self.websocket_connections[key]

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
        Returns a dict with 'status' and 'exchanges' if the WebSocket for the specified symbol is active,
        otherwise returns 'stopped' status.
        """
        running_exchanges = []
        for (exchange, sym), ws in self.websocket_connections.items():
            if sym == symbol:
                if (hasattr(ws, 'sock') and ws.sock is not None and ws.sock.connected) or ws:
                    running_exchanges.append(exchange)
        
        return {
            'status': 'running' if running_exchanges else 'stopped',
            'exchanges': running_exchanges
        }

    def get_all_symbols_status(self):
        """
        Returns a dict of symbol -> {'status': 'running'/'stopped', 'exchanges': [exchange_names]} 
        for each active WebSocket.
        """
        status = {}
        # First collect all exchanges for each symbol
        for (exchange, sym), ws in self.websocket_connections.items():
            if sym not in status:
                status[sym] = {'exchanges': []}
            
            if (hasattr(ws, 'sock') and ws.sock is not None and ws.sock.connected) or ws:
                status[sym]['exchanges'].append(exchange)
        
        # Then set the status based on whether there are any running exchanges
        for sym in status:
            status[sym]['status'] = 'running' if status[sym]['exchanges'] else 'stopped'
        
        return status

# Global instance for API control
grid_bot = GridBot()