import websocket  # pip install websocket-client
import threading
import logging
import json
import math
import time
import requests
import hashlib
import hmac
from database import crud, models, schemas
from database.database import SessionLocal
from decimal import Decimal, ROUND_DOWN
from websocket import WebSocketApp
import zlib  # added for decompression

logger = logging.getLogger(__name__)


def round_price(price, tick_size):
    # Calculate the number of decimals from tick_size (e.g. tick_size=0.01 -> 2 decimals)
    decimals = int(round(-math.log10(tick_size)))
    return round(price, decimals)

def run_bot_with_websocket(exchange_instance, symbol, amount, db_session, bot_instance):
    try:
        # Fetch all markets
        markets = exchange_instance.fetch_markets()

        # Find the symbol info for the specific symbol
        symbol_info = next((m for m in markets if m["symbol"] == symbol), None)

        # Check if the symbol exists
        if not symbol_info:
            logger.error(f"Symbol {symbol} not found on {exchange_instance.name or exchange_instance.id}.")
            return None

        # Extract step_size, tick_size, and min_notional
        # Use ccxt's precision.amount if available, otherwise fall back to BitMart's base_min_size
        step_size = float(symbol_info["precision"].get("amount", symbol_info.get("base_min_size", 0.00000001)))

        # Use ccxt's precision.price if available, otherwise fall back to BitMart's quote_increment
        tick_size = float(symbol_info["precision"].get("price", symbol_info.get("quote_increment", 0.00000001)))

        # Use ccxt's limits.cost.min if available, otherwise fall back to BitMart's min_buy_amount
        min_notional = float(symbol_info["limits"]["cost"].get("min", symbol_info.get("min_buy_amount", 0.0)))

        # Log or use the extracted values
        bot_config = crud.get_bot_config_by_exchange_symbol(db_session, exchange_instance.id, symbol)

        if not bot_config:
            api_key = crud.get_api_key_by_exchange(db_session, exchange_instance.id)
            if not api_key:
                logger.error(f"No API key found for exchange {exchange_instance.id}. Please create an API key first.")
                return None

            symbol_record = crud.add_symbol(db_session, symbol)
            if symbol_record is None:
                symbol_record = db_session.query(models.Symbol).filter(models.Symbol.symbol == symbol).first()

            existing_bot_config = db_session.query(models.ExchangeBotConfig).first()
            if existing_bot_config:
                config_data = schemas.ExchangeBotConfigCreate(
                    exchange_id=api_key.id,
                    symbol_id=symbol_record.id,
                    amount=existing_bot_config.amount,
                    tp_percent=existing_bot_config.tp_percent,
                    sl_percent=existing_bot_config.sl_percent,
                    tp_levels_json=existing_bot_config.tp_levels_json,
                    sl_levels_json=existing_bot_config.sl_levels_json
                )

            bot_config = crud.create_bot_config(db_session, config_data)

        tp_percent = bot_config.tp_percent
        sl_percent = bot_config.sl_percent

        open_orders = exchange_instance.fetch_open_orders(symbol)
        open_order_prices = {float(o.get('price', 0)) for o in open_orders}
        tp_levels = json.loads(bot_config.tp_levels_json or '[]')
        sl_levels = json.loads(bot_config.sl_levels_json or '[]')

        # If no TP/SL levels exist, reset the grid.
        if not tp_levels and not sl_levels:
            logger.info("No TP/SL levels found. Resetting orders.")
            for order in open_orders:
                order_id = order.get('id')
                if order_id:
                    exchange_instance.cancel_order(order_id, symbol)
                    logger.info(f"Cancelled order {order_id}")

            initialize_orders(
                exchange_instance, symbol, amount, tp_percent, sl_percent,
                step_size, tick_size, min_notional, db_session, bot_config
            )
        else:
            logger.info(f"Checking stored TP: {tp_levels}, stored SL: {sl_levels}")
            logger.info(f"Open orders found: {[o.get('price', 0) for o in open_orders]}")

            tp_missing = [p for p in tp_levels if p not in open_order_prices]
            sl_missing = [p for p in sl_levels if p not in open_order_prices]

            logger.info(f"tp_missing = {tp_missing}, sl_missing = {sl_missing}")

            # If no TP levels exist, we need to reset the grid.
            if not tp_levels:
                logger.info("No TP levels stored; resetting the grid.")
                for order in open_orders:
                    order_id = order.get('id')
                    if order_id:
                        logger.info(f"Cancelling order ID: {order_id} at price {order.get('price', 0)}")
                        exchange_instance.cancel_order(order_id, symbol)
                initialize_orders(
                    exchange_instance, symbol, amount, tp_percent, sl_percent,
                    step_size, tick_size, min_notional, db_session, bot_config
                )
            # If TP levels exist and all are missing (i.e. fully filled)
            elif len(tp_missing) == len(tp_levels):
                logger.info("TP filled; cancelling SL orders & resetting grid.")
                for order in open_orders:
                    order_id = order.get('id')
                    if order_id:
                        logger.info(f"Cancelling order ID: {order_id} at price {order.get('price', 0)}")
                        exchange_instance.cancel_order(order_id, symbol)
                initialize_orders(
                    exchange_instance, symbol, amount, tp_percent, sl_percent,
                    step_size, tick_size, min_notional, db_session, bot_config
                )
            # Otherwise, if SL orders are missing, update them...
            elif sl_missing:
                logger.info(f"Missing SL detected: {sl_missing}")
                updated_sl_prices = place_limit_buys(exchange_instance, symbol, amount, sl_missing, step_size, min_notional)
                for i, old_price in enumerate(sl_missing):
                    new_price = updated_sl_prices[i]
                    index_in_sl = sl_levels.index(old_price)
                    sl_levels[index_in_sl] = new_price
                bot_config.sl_levels_json = json.dumps(sl_levels)
                db_session.commit()
            # And if only TP orders are missing...
            elif tp_missing and not sl_missing:
                logger.info(f"Re-placing missing TP order(s): {tp_missing}")
                base_asset, _ = symbol.split('/')
                balance = exchange_instance.fetch_balance()
                base_balance = balance.get(base_asset, {}).get('free')
                if base_balance > 0:
                    missing_tp_price = tp_missing[0]
                    new_price = place_limit_sell(exchange_instance, symbol, base_balance, missing_tp_price, step_size)
                    idx = tp_levels.index(missing_tp_price)
                    tp_levels[idx] = new_price
                    bot_config.tp_levels_json = json.dumps(tp_levels)
                    db_session.commit()
                else:
                    logger.warning(f"Insufficient balance for {base_asset} to place TP order.")

        exchange_id = exchange_instance.id.lower()
        
        if exchange_id == "binance":
            ws = start_binance_websocket(
                exchange_instance, symbol, bot_config.id, amount,
                step_size, tick_size, min_notional, sl_percent, tp_percent, True, db_session
            )
        elif exchange_id == "bitmart":
            ws = start_bitmart_websocket(
                exchange_instance, symbol, bot_config.id, amount,
                step_size, tick_size, min_notional, sl_percent, tp_percent
            )
        elif exchange_id == "gateio":
            ws = start_gateio_websocket(
                exchange_instance, symbol, bot_config.id, amount,
                step_size, tick_size, min_notional, sl_percent, tp_percent
            )
        elif exchange_id == "bybit":
            ws = start_bybit_websocket(
                exchange_instance, symbol, bot_config.id, amount,
                step_size, tick_size, min_notional, sl_percent, tp_percent
            )
        else:
            logger.warning(f"No websocket method implemented for exchange: {exchange_id}")
            return None

        if not hasattr(bot_instance, 'websocket_connections'):
            bot_instance.websocket_connections = {}
        bot_instance.websocket_connections[(exchange_instance.id, symbol)] = ws

        return ws
    except Exception as e:
        logger.exception(f"Error encountered: {repr(e)}")
        return None

    finally:
        db_session.close()
        
def initialize_orders(exchange, symbol, amount, tp_percent, sl_percent,
                      step_size, tick_size, min_notional, db_session, bot_config):
    """
    Creates fresh orders (1 Market Buy, 1 TP, 3 SL).
    """
    base_asset, _ = symbol.split('/')
    current_price = exchange.fetch_ticker(symbol)['last']
    order_size = math.floor((amount / current_price) / step_size) * step_size

    if min_notional and order_size * current_price < min_notional:
        logger.error("Order size below min_notional; cannot proceed.")
        return

    params = {}
    if exchange.id == 'gateio' or exchange.id == 'bitmart':
        params['createMarketBuyOrderRequiresPrice'] = False

    if exchange.id == 'bitmart' or exchange.id == 'gateio':
        order_size = amount
    # --- Proceed with your market buy ---
    exchange.create_market_buy_order(symbol, order_size, params=params)
    logger.info(f"{exchange.id}:r Market buy executed: {order_size} {base_asset} @ {current_price}")

    # The "intended" prices
    intended_tp = round_price(current_price * (1 + tp_percent / 100), tick_size)
    intended_sls = [
        round_price(current_price * (1 - sl_percent / 100) ** (i + 1), tick_size)
        for i in range(3)
    ]
    
    balance = exchange.fetch_balance()
    base_balance = balance.get(base_asset, {}).get('free', order_size)  # Avoid KeyError

    # Place TP & SL orders, then store them
    actual_tp_price = place_limit_sell(exchange, symbol, base_balance, intended_tp, step_size)
    actual_sl_prices = place_limit_buys(exchange, symbol, amount, intended_sls, step_size, min_notional)

    bot_config.tp_levels_json = json.dumps([actual_tp_price])
    bot_config.sl_levels_json = json.dumps(actual_sl_prices)
    logger.info(f"Started Grid: TP Levels: {bot_config.tp_levels_json} / Stop Loss Levels: {bot_config.sl_levels_json} ")
    db_session.commit()

def place_limit_sell(exchange, symbol, amount, price, step_size):
    amount = Decimal(str(amount)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision
    price = Decimal(str(price))  # Convert price to Decimal
    
    params = {}
    if exchange.id == "bybit":
        params["timeInForce"] = "GTC"  # Ensure order stays active until filled
    
    try:
        order = exchange.create_limit_sell_order(symbol, float(amount), float(price), params=params)
        if order and isinstance(order, dict) and "price" in order:
            final_price = float(order["price"])
            logger.info(f"{exchange.id}: Limit sell placed: {amount} @ {final_price}")
            return final_price
        else:
            logger.error(f"Limit sell order creation returned unexpected response: {order}")
            return float(price)  # Fallback
    except Exception as e:
        logger.error(f"{exchange.id}: Limit sell error {amount} @ {price}: {repr(e)}")
        return float(price)  # Fallback
    
def place_limit_buys(exchange, symbol, total_usdt, prices, step_size, min_notional):
    final_prices = []
    for p in prices:
        p = Decimal(str(p))  # Ensure price is also a Decimal
        amount = Decimal(total_usdt) / p  # Convert total_usdt to Decimal before division
        amount = amount.quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision
        
        params = {}
        if exchange.id == "bybit":
            params["timeInForce"] = "GTC"  # Ensure order stays active until filled
        
        if not min_notional or (amount * p) >= Decimal(str(min_notional)):  # Convert min_notional to Decimal
            try:
                order = exchange.create_limit_buy_order(symbol, float(amount), float(p), params=params)
                if order and isinstance(order, dict) and "price" in order:
                    final_price = float(order["price"])
                    logger.info(f"{exchange.id}: Limit buy placed: {amount} @ {final_price}")
                    final_prices.append(final_price)
                else:
                    logger.error(f"Limit buy order creation returned unexpected response: {order}")
                    final_prices.append(float(p))  # Fallback
            except Exception as e:
                logger.error(f"{exchange.id}: Limit buy error @ {p}: {repr(e)}")
                final_prices.append(float(p))  # Convert Decimal back to float for consistency
        else:
            logger.warning(f"Skipping SL @ {p} due to min_notional check.")
            final_prices.append(float(p))

    return final_prices

def get_binance_listen_key(api_key):
    """ Get a listenKey from Binance via POST /api/v3/userDataStream. """
    url = "https://api.binance.com/api/v3/userDataStream"
    headers = {
        "X-MBX-APIKEY": api_key
    }
    try:
        response = requests.post(url, headers=headers, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data["listenKey"]
    except Exception as e:
        raise RuntimeError(f"Error fetching listenKey: {e}")

def keepalive_binance_listen_key(api_key, listen_key):
    """ Keep a listenKey alive via PUT /api/v3/userDataStream """
    url = "https://api.binance.com/api/v3/userDataStream"
    headers = {
        "X-MBX-APIKEY": api_key
    }
    params = {
        "listenKey": listen_key
    }
    try:
        response = requests.put(url, headers=headers, params=params, timeout=5)
        response.raise_for_status()
        logger.info(f"✅ Successfully kept listenKey alive: {listen_key}")
    except Exception as e:
        logger.error(f"❌ Failed to keep listenKey alive: {e}")

def schedule_listen_key_keepalive(api_key, listen_key, interval=1800):
    """
    Schedule the keep-alive call every `interval` seconds (default 30 min).
    Continues until program exit or you stop it manually.
    """
    def keepalive_loop():
        while True:
            keepalive_binance_listen_key(api_key, listen_key)
            time.sleep(interval)

    t = threading.Thread(target=keepalive_loop, daemon=True)
    t.start()

def start_binance_websocket(exchange_instance, symbol, bot_config_id, amount,
                            step_size, tick_size, min_notional,
                            sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                            auto_reconnect=True, db_session=None):
    """
    Starts a Binance WebSocket connection for user data stream.
    """

    # ✅ Fetch bot config from the database
    session = db_session or SessionLocal()
    bot_config = session.query(models.ExchangeBotConfig)\
                        .filter(models.ExchangeBotConfig.id == bot_config_id).first()

    if not bot_config or not bot_config.exchange_api_key:
        logger.error(f"❌ No API key found for exchange {exchange_instance.id}. Please create an API key first.")
        session.close()
        return None

    api_key = bot_config.exchange_api_key.api_key  # ✅ Get the API key correctly

    # 🔥 Get listenKey manually
    try:
        listen_key = get_binance_listen_key(api_key)
    except Exception as e:
        logger.error(f"❌ Failed to get listenKey: {e}")
        session.close()
        return None

    # ✅ Start the keep-alive scheduling in the background
    schedule_listen_key_keepalive(api_key, listen_key, interval=1800)  # 30 min

    ws_url = f"wss://stream.binance.com:9443/ws/{listen_key}"
    session.close()  # ✅ Close session after fetching config

    def on_open(ws):
        logger.info(f"✅ WebSocket connected to {ws_url}")

    def on_message(ws, message):
        try:
            data = json.loads(message)
        except Exception as e:
            logger.error(f"❌ Error parsing message: {e}")
            return

        # Respond to ping messages.
        if "ping" in data:
            ws.send(json.dumps({"pong": data["ping"]}))
            return

        # Only process executionReport events with FILLED status.
        if data.get("e") != "executionReport" or data.get("X") != "FILLED" or data.get("s") != symbol:
            return

        try:
            logger.info(f"Binance: Order filled: {data}")
            current_price = float(data.get("L"))
        except Exception as e:
            logger.error(f"❌ Error extracting current price: {e}")
            return

        process_order_update(
            exchange_instance, symbol, bot_config_id, amount,
            step_size, tick_size, min_notional,
            sl_buffer_percent, sell_rebound_percent,
            current_price
        )

    def on_error(ws, error):
        logger.error(f"🚨 Binance WebSocket error: {error}")
        # If auto-reconnect is enabled, force closure to trigger on_close
        if getattr(ws, "auto_reconnect", True):
            ws.close()

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ Binance WebSocket closed: {close_status_code}, {close_msg}")

        # ✅ Close WebSocket connection explicitly
        ws.close()

        # If auto_reconnect is disabled, close orders and stop
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
            return
        else:
            logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")

        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")
        
        threading.Timer(
            reconnect_delay,
            lambda: start_binance_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=auto_reconnect,
                db_session=db_session  
            )
        ).start()

    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.auto_reconnect = auto_reconnect

    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()

    logger.info(f"🚀 Started Binance WebSocket for {symbol}. Listening for price movements...")
    return ws

def start_bitmart_websocket(exchange_instance, symbol, bot_config_id, amount,
                              step_size, tick_size, min_notional, 
                              sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                              auto_reconnect=True, db_session=None):
    """
    Starts a BitMart WebSocket connection with authentication.
    """
    # Retrieve API credentials from DB.
    session = db_session or SessionLocal()
    bot_config = session.query(models.ExchangeBotConfig)\
                        .filter(models.ExchangeBotConfig.id == bot_config_id).first()
    if not bot_config or not bot_config.exchange_api_key:
        logger.error(f"❌ No API key found for exchange {exchange_instance.id}. Please create an API key first.")
        session.close()
        return None

    api_key = bot_config.exchange_api_key.api_key
    api_secret = bot_config.exchange_api_key.api_secret
    api_memo = "bua"  # as defined in your original logic
    session.close()

    # Ping/Pong configuration
    PING_INTERVAL = 15  # seconds to wait before sending a ping if no message is received.
    PONG_TIMEOUT = 15   # seconds to wait for a pong response.

    def generate_sign(timestamp: str, memo: str, secret: str) -> str:
        message = f"{timestamp}#{memo}#bitmart.WebSocket"
        return hmac.new(secret.encode("utf-8"),
                        message.encode("utf-8"),
                        digestmod=hashlib.sha256).hexdigest()

    def reset_ping_timer(ws):
        if hasattr(ws, "ping_timer") and ws.ping_timer is not None:
            ws.ping_timer.cancel()
        ws.ping_timer = threading.Timer(PING_INTERVAL, lambda: ping_handler(ws))
        ws.ping_timer.daemon = True
        ws.ping_timer.start()

    def ping_handler(ws):
        try:
            ws.send("ping")
            ws.waiting_for_pong = True
            ws.pong_timer = threading.Timer(PONG_TIMEOUT, lambda: pong_timeout_handler(ws))
            ws.pong_timer.daemon = True
            ws.pong_timer.start()
        except Exception as e:
            logger.error(f"Error sending ping: {e}")

    def pong_timeout_handler(ws):
        if getattr(ws, "waiting_for_pong", False):
            logger.warning("Pong not received in time. Closing connection...")
            ws.close()

    def message_handler(msg):
        try:
            if "data" in msg and isinstance(msg["data"], list) and msg["data"]:
                order_data = msg["data"][0]
                order_state = order_data.get("order_state")
                if order_state in ["filled"]:
                    price = float(order_data.get("price", 0))
                    if price == 0:
                        price = float(order_data.get("last_fill_price", 0))
                    current_price = price
                    logger.info(f"BitMart WebSocket: {order_data.get('side')} has been triggered at {order_data.get('price')} vs current price {current_price} | Placing new orders")
                    process_order_update(
                        exchange_instance, symbol, bot_config_id, amount,
                        step_size, tick_size, min_notional, 
                        sl_buffer_percent, sell_rebound_percent, 
                        current_price
                    )
        except Exception as e:
            logger.error(f"❌ Error processing BitMart WebSocket message: {e}")

    def on_open(ws):
        logger.info("WebSocket opened, sending login message...")
        timestamp = str(int(time.time() * 1000))
        sign = generate_sign(timestamp, api_memo, api_secret)
        login_payload = {"op": "login", "args": [api_key, timestamp, sign]}
        ws.send(json.dumps(login_payload))
        logger.info(f"Login message sent: {login_payload}")
        reset_ping_timer(ws)

    def on_message(ws, message):
        # Decompress if message is binary (compressed)
        if isinstance(message, bytes):
            try:
                # Negative window bits indicates raw DEFLATE stream
                message = zlib.decompress(message, -zlib.MAX_WBITS).decode("utf-8")
            except Exception as e:
                logger.error(f"Error decompressing message: {e}")
                reset_ping_timer(ws)
                return

        if message.strip() == "pong":
            ws.waiting_for_pong = False
            if hasattr(ws, "pong_timer") and ws.pong_timer is not None:
                ws.pong_timer.cancel()
            reset_ping_timer(ws)
            return

        try:
            msg = json.loads(message)
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            reset_ping_timer(ws)
            return

        if msg.get("event") == "login":
            subscription_payload = {
                "op": "subscribe",
                "args": [f"spot/user/order:{symbol.replace('/', '_')}"]
            }
            ws.send(json.dumps(subscription_payload))
            logger.info(f"Subscription message sent: {subscription_payload}")

        message_handler(msg)
        reset_ping_timer(ws)

    def on_error(ws, error):
        logger.error(f"🚨 BitMart WebSocket error: {error}")
        if not getattr(ws, "auto_reconnect", False):
            ws.close()

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ BitMart WebSocket closed for {symbol}. Reason: {close_status_code} - {close_msg}")
        try:
            ws.close()
        except Exception as e:
            logger.error(f"Error stopping WebSocket: {e}")

        # Check the current instance attribute
        if not getattr(ws, "auto_reconnect", False):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
            return

        logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")
        # When reconnecting, we always pass auto_reconnect=True because a new connection should be healthy.
        threading.Timer(
            reconnect_delay,
            lambda: start_bitmart_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=True,
                db_session=db_session
            )
        ).start()

    logger.info("Connecting to BitMart WebSocket via WebSocketApp...")
    ws_app = websocket.WebSocketApp(
        "wss://ws-manager-compress.bitmart.com/user?protocol=1.1",
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    
    ws_app.auto_reconnect = auto_reconnect

    # Run the WebSocket in a background thread so that the call is non-blocking.
    ws_thread = threading.Thread(target=lambda: ws_app.run_forever(), daemon=True)
    ws_thread.start()
    return ws_app

def start_gateio_websocket(exchange_instance, symbol, bot_config_id, amount,
                           step_size, tick_size, min_notional, 
                           sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                           auto_reconnect=True, db_session=None):
    """
    Starts a Gate.io WebSocket connection with authentication for trade updates.
    """
    ws_url = "wss://api.gateio.ws/ws/v4/"
    channel_symbol = symbol.replace("/", "_")

    session = db_session or SessionLocal()
    bot_config = session.query(models.ExchangeBotConfig).filter(models.ExchangeBotConfig.id == bot_config_id).first()

    if not bot_config or not bot_config.exchange_api_key:
        logger.error(f"❌ No API key found for exchange {exchange_instance.id}. Please create an API key first.")
        session.close()
        return None

    api_key = bot_config.exchange_api_key.api_key
    api_secret = bot_config.exchange_api_key.api_secret
    session.close()

    class GateWebSocketApp(WebSocketApp):
        def __init__(self, url, api_key, api_secret, **kwargs):
            super(GateWebSocketApp, self).__init__(url, **kwargs)
            self._api_key = api_key
            self._api_secret = api_secret
            self.auto_reconnect = auto_reconnect  # ✅ Ensure auto_reconnect is respected
            self.last_ping_tm = time.time()  # Track last ping timestamp

        def get_sign(self, channel, event, timestamp):
            """Generate HMAC signature for authentication."""
            message = f"channel={channel}&event={event}&time={timestamp}"
            h = hmac.new(self._api_secret.encode("utf8"), message.encode("utf8"), hashlib.sha512)
            return h.hexdigest()

        def send_auth_request(self):
            """Sends authentication request to subscribe to trade updates."""
            timestamp = int(time.time())
            auth_data = {
                "time": timestamp,
                "channel": "spot.usertrades",
                "event": "subscribe",
                "payload": [channel_symbol],
                "auth": {
                    "method": "api_key",
                    "KEY": self._api_key,
                    "SIGN": self.get_sign("spot.usertrades", "subscribe", timestamp),
                }
            }
            self.send(json.dumps(auth_data))
            logger.info("🔐 Sent authentication request.")

        def send_ping(self):
            """
            Sends a 'ping' every 15 seconds to keep the connection alive.
            """
            while True:
                time.sleep(15)
                if time.time() - self.last_ping_tm > 15:
                    try:
                        self.send(json.dumps({"channel": "spot.ping", "event": None}))
                    except Exception as e:
                        logger.error(f"❌ Error sending ping: {e}")
                        break

    def on_open(ws):
        """Handles WebSocket connection opening."""
        logger.info("✅ Gate.io WebSocket connected.")
        ws.send_auth_request()
        threading.Thread(target=ws.send_ping, daemon=True).start()

    def on_message(ws, message):
        """Processes incoming WebSocket messages."""
        try:
            data = json.loads(message)
            if "result" in data and isinstance(data["result"], list) and data["result"]:
                trade = data["result"][0]
                current_price = float(trade["price"])
                process_order_update(
                    exchange_instance, symbol, bot_config_id, amount, 
                    step_size, tick_size, min_notional, 
                    sl_buffer_percent, sell_rebound_percent, current_price
                )
        except Exception as e:
            logger.error(f"❌ Error processing Gate.io WebSocket message: {e}")

    def on_close(ws, close_status_code, close_msg):
        """Handles WebSocket closure logic."""
        logger.warning(f"❌ Gate.io WebSocket Closed: {close_status_code}, {close_msg}")

        if ws is None:
            logger.error("⚠️ WebSocket instance is None during closure.")
            return

        try:
            ws.close()
        except Exception as e:
            logger.error(f"❌ Error closing WebSocket: {e}")

        # ✅ Prevent reconnection if auto_reconnect is disabled
        if not getattr(ws, "auto_reconnect", False):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
            return  # ✅ Stop execution

        # ✅ Handle reconnection
        logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        reconnect_delay = 5  # seconds
        logger.info(f"🔄 Reconnecting in {reconnect_delay} seconds...")

        threading.Timer(reconnect_delay, lambda: start_gateio_websocket(
            exchange_instance, symbol, bot_config_id, amount,
            step_size, tick_size, min_notional,
            sl_buffer_percent, sell_rebound_percent,
            auto_reconnect=auto_reconnect,
            db_session=db_session
        )).start()

    def on_error(ws, error):
        """Handles WebSocket errors."""
        logger.error(f"🚨 Gate.io WebSocket Error: {error}")
        if not getattr(ws, "auto_reconnect", auto_reconnect):
            ws.close()  # ✅ Trigger on_close()

    # ✅ Create WebSocket instance and return it
    ws = GateWebSocketApp(
        ws_url,
        api_key,
        api_secret,
        on_open=on_open,
        on_message=on_message,
        on_close=on_close,
        on_error=on_error,
    )

    ws.auto_reconnect = auto_reconnect  # ✅ Ensure WebSocket respects auto-reconnect
    threading.Thread(target=ws.run_forever, daemon=True).start()
    logger.info(f"🚀 Started Gate.io WebSocket for {symbol}. Listening for price movements...")

    return ws  # ✅ Return the WebSocket instance

def start_bybit_websocket(exchange_instance, symbol, bot_config_id, amount,
                          step_size, tick_size, min_notional, 
                          sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                          auto_reconnect=True, db_session=None):
    """
    Starts a Bybit WebSocket connection for SPOT orders using the websocket-client library.
    """
    # Retrieve bot config and API credentials.
    session = db_session or SessionLocal()
    bot_config = session.query(models.ExchangeBotConfig).filter(
        models.ExchangeBotConfig.id == bot_config_id
    ).first()

    if not bot_config or not bot_config.exchange_api_key:
        logger.error(f"❌ No API key found for exchange {exchange_instance.id}. Please create an API key first.")
        session.close()
        return None

    api_key = bot_config.exchange_api_key.api_key
    api_secret = bot_config.exchange_api_key.api_secret
    session.close()

    ws_url = "wss://stream.bybit.com/v5/private"  # Change to testnet URL if needed

    def generate_signature(secret, expires):
        payload = f"GET/realtime{expires}"
        return hmac.new(secret.encode("utf-8"),
                        payload.encode("utf-8"),
                        digestmod=hashlib.sha256).hexdigest()

    def on_open(ws):
        logger.info("🚀 Bybit WebSocket connection opened, sending auth and subscription...")
        # Authenticate
        expires = int((time.time() + 10) * 1000)  # Expires 10 seconds from now
        signature = generate_signature(api_secret, expires)
        auth_payload = {
            "req_id": "10001",
            "op": "auth",
            "args": [api_key, expires, signature]
        }
        ws.send(json.dumps(auth_payload))

        # Subscribe to order stream
        subscribe_payload = {
            "op": "subscribe",
            "args": ["order"]
        }
        ws.send(json.dumps(subscribe_payload))

        # Start a ping loop: send ping every 20 seconds.
        def send_ping():
            while True:
                time.sleep(20)
                try:
                    ws.send(json.dumps({"op": "ping"}))
                except Exception as e:
                    logger.error(f"Error sending ping: {e}")
                    break

        ping_thread = threading.Thread(target=send_ping, daemon=True)
        ping_thread.start()

    def on_message(ws, message):
        try:
            msg_json = json.loads(message)
        except Exception as e:
            logger.error(f"❌ Error parsing message: {e}")
            return

        # Handle auth/subscription responses.
        if "op" in msg_json and msg_json["op"] in ["auth", "subscribe"]:
            if not msg_json.get("success", False):
                logger.error(f"❌ {msg_json['op']} failed: {msg_json.get('ret_msg', '')}")
            else:
                logger.info(f"✅ {msg_json['op']} successful.")
            return

        # Process order updates.
        if "data" not in msg_json or not isinstance(msg_json["data"], list) or not msg_json["data"]:
            return

        order_data = msg_json["data"][0]
        order_status = order_data.get("orderStatus", order_data.get("status", ""))
        order_symbol = order_data.get("symbol", "").replace("/", "")

        if order_symbol == symbol.replace("/", "") and order_status in ["Filled", "PartiallyFilledCanceled"]:
            price = order_data.get("price")
            current_price = float(price) if price is not None else 0.0

            if current_price == 0:
                avg_price = order_data.get("avgPrice")
                if avg_price is not None:
                    current_price = float(avg_price)
            logger.info(f"✅ Order processed: {order_data} at price {current_price} vs Order price: {order_data.get('price')}")
            process_order_update(
                exchange_instance, symbol, bot_config_id, amount, 
                step_size, tick_size, min_notional, 
                sl_buffer_percent, sell_rebound_percent, current_price
            )

    def on_error(ws, error):
        logger.error(f"🚨 WebSocket error: {error}")
        if getattr(ws, "auto_reconnect", False):
            on_close(ws, None, str(error))
        else:
            ws.close()

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ WebSocket closed for {symbol} (code: {close_status_code}, msg: {close_msg})")
        try:
            ws.close()
        except Exception as e:
            logger.error(f"Error during ws.close(): {e}")

        # Check the current value of auto_reconnect.
        if not getattr(ws, "auto_reconnect", False):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
            return  # Stop execution to prevent reconnection.

        logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")

        # When reconnecting, we pass auto_reconnect=True for a fresh connection.
        threading.Timer(
            reconnect_delay,
            lambda: start_bybit_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=True,
                db_session=db_session
            )
        ).start()

    logger.info("🚀 Connecting to Bybit WebSocket via WebSocketApp...")
    ws_app = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Start the WebSocket in a background thread.
    ws_thread = threading.Thread(target=lambda: ws_app.run_forever(), daemon=True)
    ws_thread.start()

    return ws_app

def process_order_update(exchange_instance, symbol, bot_config_id, amount, step_size,
                         tick_size, min_notional, sl_buffer_percent, sell_rebound_percent, current_price):
    session = None
    try:
        session = SessionLocal()
        bot_config = session.query(models.ExchangeBotConfig).filter(models.ExchangeBotConfig.id == bot_config_id).first()
        if not bot_config:
            logger.error(f"⚠️ Bot config with ID {bot_config_id} not found.")
            return

        tp_levels = json.loads(bot_config.tp_levels_json)
        sl_levels = json.loads(bot_config.sl_levels_json)

        for i in range(len(tp_levels)):
            if current_price >= tp_levels[i]:
                triggered_tp = tp_levels.pop(i)
                bot_config.tp_levels_json = json.dumps(tp_levels)
                session.commit()
                logger.info(f"🎯 Price {current_price} hit TP {triggered_tp}")

                # If i == 0, it means that was the last TP
                if i == 0:
                    logger.info("All TPs filled! -> Resetting grid after delay.")
                    try:
                        open_orders = exchange_instance.fetch_open_orders(symbol)
                        for order in open_orders:
                            exchange_instance.cancel_order(order['id'], symbol)
                            logger.info(f"🛑 Cancelled order {order['id']}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling orders: {e}")
                    
                    initialize_orders(
                        exchange_instance,
                        symbol,
                        amount,
                        bot_config.tp_percent,
                        bot_config.sl_percent,
                        step_size,
                        tick_size,
                        min_notional,
                        session,
                        bot_config
                    )
                    return

                new_sl_price = round_price(triggered_tp * (1 - sl_buffer_percent / 100), tick_size)

                # Here we remove the old SL and cancel it before placing the new SL
                if sl_levels:
                    last_sl = min(sl_levels)
                    sl_levels.remove(last_sl)

                    # Cancel the buy order matching last_sl
                    try:
                        open_orders = exchange_instance.fetch_open_orders(symbol)
                        buy_orders = [o for o in open_orders if o.get('side', '').lower() == 'buy']
                        tolerance = 1e-8
                        order_to_cancel = None
                        for o in buy_orders:
                            if abs(float(o.get('price', 0)) - last_sl) < tolerance:
                                order_to_cancel = o
                                break

                        if order_to_cancel:
                            exchange_instance.cancel_order(order_to_cancel['id'], symbol)
                            logger.info(f"🛑 Cancelled last SL buy order {order_to_cancel['id']} @ {order_to_cancel['price']}")
                        else:
                            logger.warning(f"⚠️ No buy order found matching price {last_sl}")
                    except Exception as e:
                        logger.error(f"❌ Error cancelling last SL buy order @ {last_sl}: {e}")

                sl_levels.insert(0, new_sl_price)
                # Place the new limit buy in 0.5s
                threading.Timer(
                    0.5,
                    place_limit_buys,
                    args=(exchange_instance, symbol, amount, [new_sl_price], tick_size, min_notional)
                ).start()
                logger.info(f"{bot_config_id}: Checking stored TP: {tp_levels}, stored SL: {sl_levels}")

                bot_config.sl_levels_json = json.dumps(sl_levels)
                session.commit()
                break

        # SL logic remains unchanged
        for sl_price in sl_levels:
            if current_price <= sl_price:
                last_sl = min(sl_levels)
                new_sl_price = round_price(last_sl * (1 - sl_buffer_percent / 100), tick_size)
                new_sell_price = round_price(sl_price * (1 + sell_rebound_percent / 100), tick_size)
                base_asset, _ = symbol.split('/')
                balance = exchange_instance.fetch_balance()
                base_balance = balance.get(base_asset, {}).get('free', 0)
                
                threading.Timer(
                    0.5,
                    place_limit_buys,
                    args=(exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional)
                ).start()
                threading.Timer(
                    0.5,
                    place_limit_sell,
                    args=(exchange_instance, symbol, base_balance, new_sell_price, step_size)
                ).start()
                
                sl_levels.remove(sl_price)
                sl_levels.append(new_sl_price)
                sl_levels.sort(reverse=True)
                bot_config.sl_levels_json = json.dumps(sl_levels)

                tp_levels.append(new_sell_price)
                tp_levels.sort(reverse=True)
                bot_config.tp_levels_json = json.dumps(tp_levels)
                session.commit()
                logger.info(f"{exchange_instance.id}: Checking stored TP: {tp_levels}, stored SL: {sl_levels}")

                break

    except Exception as e:
        logger.error(f"❌ Error processing order update: {e}")
    finally:
        if session:
            session.close()
            
def close_and_sell_all(exchange_instance, symbol):
    try:
        open_orders = exchange_instance.fetch_open_orders(symbol)
        for order in open_orders:
            exchange_instance.cancel_order(order['id'], symbol)
            logger.info(f"🛑 Cancelled order {order['id']}")
        base_asset, quote_asset = symbol.split('/')
        balance = exchange_instance.fetch_balance()
        base_balance = balance.get(base_asset, {}).get('free')
        if base_balance > 0:
            sell_order = exchange_instance.create_market_sell_order(symbol, base_balance)
            logger.info(f"💰 Sold {base_balance} {base_asset} for USDT")
        else:
            logger.info(f"⚠️ No {base_asset} balance to sell.")
    except Exception as e:
        logger.error(f"❌ Error during close_and_sell_all: {e}")
