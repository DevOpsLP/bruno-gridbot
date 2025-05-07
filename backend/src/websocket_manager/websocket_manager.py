import websocket  # pip install websocket-client
from websocket import WebSocketApp  # Add this import
import threading
import logging
import json
import math
import time
import requests
import hashlib
import hmac
import zlib  # added for decompression
from src.utils.trade_normalizers import process_trade_message
from database import crud, models, schemas
from database.database import SessionLocal
from decimal import Decimal, ROUND_DOWN

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
        initialization_success = True
        if not tp_levels and not sl_levels:
            logger.info("No TP/SL levels found. Resetting orders.")
            initialization_success = initialize_orders(
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
                initialization_success = initialize_orders(
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
                initialization_success = initialize_orders(
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

        # If initialization failed, don't start the websocket
        if not initialization_success:
            logger.error("Order initialization failed. Not starting WebSocket.")
            return None

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
                exchange_instance,
                symbol,
                bot_config.id,
                amount,
                step_size,
                tick_size,
                min_notional,
                bot_instance.websocket_connections,      # ← registry dict
                sl_buffer_percent=sl_percent,    # now floats go into the right params
                sell_rebound_percent=tp_percent,
                auto_reconnect=True,
                db_session=db_session
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
    base_asset, quote_asset = symbol.split('/')
    current_price = exchange.fetch_ticker(symbol)['last']
    order_size = math.floor((amount / current_price) / step_size) * step_size

    if min_notional and order_size * current_price < min_notional:
        logger.error("Order size below min_notional; cannot proceed.")
        return False

    params = {}
    if exchange.id == 'gateio' or exchange.id == 'bitmart':
        params['createMarketBuyOrderRequiresPrice'] = False

    if exchange.id == 'bitmart' or exchange.id == 'gateio':
        order_size = amount
        
    # Use the existing close_and_sell_all function to cancel orders and sell positions
    try:
        logger.info("Closing all existing orders and selling positions")
        close_and_sell_all(exchange, symbol)
        
        # Wait for operations to complete
        time.sleep(2)
        
        # Check available balance after selling all positions
        balance = exchange.fetch_balance()
        quote_balance = balance.get(quote_asset, {}).get('free', 0)
        logger.info(f"Available {quote_asset} balance after closing positions: {quote_balance}")
        
        if quote_balance < amount:
            logger.error(f"Insufficient {quote_asset} balance ({quote_balance}) for order of {amount}")
            return False
            
    except Exception as e:
        logger.error(f"Error during order cancellation process: {repr(e)}")
        return False

    # --- Proceed with market buy ---
    try:
        market_order = exchange.create_market_buy_order(symbol, order_size, params=params)
        logger.info(f"{exchange.id}: Market buy executed: {order_size} {base_asset} @ {current_price}")
        logger.info(f"Market order details: {market_order}")
    except Exception as e:
        logger.error(f"Failed to create market buy order: {repr(e)}")
        return False

    # The "intended" prices
    intended_tp = round_price(current_price * (1 + tp_percent / 100), tick_size)
    intended_sls = [
        round_price(current_price * (1 - sl_percent / 100) ** (i + 1), tick_size)
        for i in range(3)
    ]
    
    # Wait briefly for the market order to settle
    time.sleep(1)
    
    balance = exchange.fetch_balance()
    base_balance = balance.get(base_asset, {}).get('free', order_size)  # Avoid KeyError
    logger.info(f"Base balance after market buy: {base_balance} {base_asset}")

    # Place TP & SL orders, then store them directly in the bot config
    actual_tp_price = place_limit_sell(exchange, symbol, base_balance, intended_tp, step_size)
    actual_sl_prices = place_limit_buys(exchange, symbol, amount, intended_sls, step_size, min_notional)

    # Update bot config with arrays directly
    bot_config.tp_levels_json = json.dumps([actual_tp_price])
    bot_config.sl_levels_json = json.dumps(actual_sl_prices)

    logger.info(f"Started Grid: TP Level: {bot_config.tp_levels_json} / Stop Loss Levels: {bot_config.sl_levels_json}")
    db_session.commit()
    return True


def place_limit_sell(exchange, symbol, amount, price, step_size):
    # Convert values to Decimal for precise comparisons and calculations
    amount = Decimal(str(amount)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision
    price = Decimal(str(price))  # Convert price to Decimal
    min_amount = Decimal(str(step_size))  # Minimum valid amount
    
    # Check for minimum valid amount (prevent zero or very small amounts)
    if amount <= Decimal('0') or amount < min_amount:
        logger.error(f"{exchange.id}: Cannot place sell order - amount {amount} is too small (minimum: {step_size})")
        return float(price)  # Return original price without placing order
    
    params = {}
    if exchange.id == "bybit":
        params["timeInForce"] = "GTC"  # Ensure order stays active until filled
    
    try:
        logger.info(f"{exchange.id}: Attempting to place sell order: {float(amount)} @ {float(price)}")
        order = exchange.create_limit_sell_order(symbol, float(amount), float(price), params=params)
        # Special handling for Bybit
        if exchange.id == "bybit":
            logger.info(f"{exchange.id}: Limit sell placed: {amount} @ {float(price)}")
            return float(price)  # Always return the original price for Bybit
        elif order and isinstance(order, dict) and "price" in order:
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
    
    # Validate inputs to prevent downstream errors
    if not prices or len(prices) == 0:
        logger.error(f"{exchange.id}: No prices provided for limit buys")
        return []
        
    if total_usdt <= 0:
        logger.error(f"{exchange.id}: Invalid total_usdt amount: {total_usdt}")
        return [float(p) for p in prices]
    
    for p in prices:
        p = Decimal(str(p))  # Ensure price is also a Decimal
        
        # Skip invalid prices
        if p <= 0:
            logger.error(f"{exchange.id}: Invalid price {p} for limit buy")
            final_prices.append(float(p))
            continue
            
        amount = Decimal(total_usdt) / p  # Convert total_usdt to Decimal before division
        amount = amount.quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision
        
        # Check for minimum valid amount
        if amount <= Decimal('0') or amount < Decimal(str(step_size)):
            logger.error(f"{exchange.id}: Cannot place buy order @ {p} - calculated amount {amount} is too small (minimum: {step_size})")
            final_prices.append(float(p))  # Add the original price without placing an order
            continue
        
        params = {}
        if exchange.id == "bybit":
            params["timeInForce"] = "GTC"  # Ensure order stays active until filled
        
        min_notional_decimal = Decimal(str(min_notional)) if min_notional else Decimal('0')
        if not min_notional_decimal or (amount * p) >= min_notional_decimal:  # Convert min_notional to Decimal
            try:
                logger.info(f"{exchange.id}: Attempting to place buy order: {float(amount)} @ {float(p)}")
                order = exchange.create_limit_buy_order(symbol, float(amount), float(p), params=params)
                # Special handling for Bybit
                if exchange.id == "bybit":
                    logger.info(f"{exchange.id}: Limit buy placed: {amount} @ {float(p)}")
                    final_prices.append(float(p))  # Always return the original price for Bybit
                elif order and isinstance(order, dict) and "price" in order:
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
        if data.get("e") != "executionReport" or data.get("X") != "FILLED" or data.get("s") != symbol.replace("/", ""):
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
        # Now, process the trade record: normalize and store the trade (with PnL calculation, etc.)
        try:
            
            # Use the API key's id from the bot config since it's stored there:
            exchange_api_key_id = bot_config.exchange_api_key.id
            process_trade_message("binance", data, db_session, exchange_api_key_id)
        except Exception as e:
            logger.error(f"Error processing trade message: {e}")
            
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
            logger.info("Binance: Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
            return
        else:
            logger.info("Binance: Connection lost but auto-reconnect is enabled; preserving orders.")

        reconnect_delay = 5  # seconds
        logger.info(f"Binance: Attempting to reconnect in {reconnect_delay} seconds...")
        
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
    PING_INTERVAL = 10  # Reduced from 15 to 10 seconds
    PONG_TIMEOUT = 20   # Increased from 15 to 20 seconds
    MAX_RETRIES = 3     # Maximum number of consecutive pong timeouts before closing

    # Add a set to track processed order IDs
    processed_orders = set()
    pong_timeout_count = 0  # Track consecutive pong timeouts

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
            if not ws.sock or not ws.sock.connected:
                logger.warning("WebSocket not connected, skipping ping")
                return
                
            ws.send("ping")
            ws.waiting_for_pong = True
            ws.pong_timer = threading.Timer(PONG_TIMEOUT, lambda: pong_timeout_handler(ws))
            ws.pong_timer.daemon = True
            ws.pong_timer.start()
        except Exception as e:
            logger.error(f"Error sending ping: {e}")

    def pong_timeout_handler(ws):
        nonlocal pong_timeout_count
        if getattr(ws, "waiting_for_pong", False):
            pong_timeout_count += 1
            logger.warning(f"Pong not received in time. Timeout count: {pong_timeout_count}/{MAX_RETRIES}")
            
            if pong_timeout_count >= MAX_RETRIES:
                logger.error("Max pong timeouts reached, closing connection...")
                ws.close()
            else:
                # Try to send another ping
                try:
                    if ws.sock and ws.sock.connected:
                        ws.send("ping")
                        ws.pong_timer = threading.Timer(PONG_TIMEOUT, lambda: pong_timeout_handler(ws))
                        ws.pong_timer.daemon = True
                        ws.pong_timer.start()
                except Exception as e:
                    logger.error(f"Error sending recovery ping: {e}")
                    ws.close()

    def message_handler(msg):
        try:
            if "data" in msg and isinstance(msg["data"], list) and msg["data"]:
                order_data = msg["data"][0]
                order_state = order_data.get("order_state")
                order_id = order_data.get("order_id")
                
                # Skip if we've already processed this order
                if order_id in processed_orders:
                    logger.debug(f"Skipping already processed order: {order_id}")
                    return
                    
                if order_state in ["filled"]:
                    price = float(order_data.get("price", 0))
                    if price == 0:
                        price = float(order_data.get("last_fill_price", 0))
                    current_price = price
                    logger.info(f"BitMart WebSocket: {order_data.get('side')} has been triggered at {order_data.get('price')} vs current price {current_price} | Placing new orders")
                    
                    # Add order ID to processed set
                    processed_orders.add(order_id)
                    
                    # Clean up old processed orders to prevent memory growth
                    if len(processed_orders) > 1000:
                        processed_orders.clear()
                    
                    process_order_update(
                        exchange_instance, symbol, bot_config_id, amount,
                        step_size, tick_size, min_notional, 
                        sl_buffer_percent, sell_rebound_percent, 
                        current_price
                    )
                    process_trade_message("bitmart", msg, db_session, bot_config.exchange_api_key.id)
        except Exception as e:
            logger.error(f"❌ Error processing BitMart WebSocket message: {e}")

    def on_open(ws):
        nonlocal pong_timeout_count
        pong_timeout_count = 0  # Reset timeout count on new connection
        logger.info("WebSocket opened, sending login message...")
        timestamp = str(int(time.time() * 1000))
        sign = generate_sign(timestamp, api_memo, api_secret)
        login_payload = {"op": "login", "args": [api_key, timestamp, sign]}
        ws.send(json.dumps(login_payload))
        logger.info(f"Login message sent: {login_payload}")
        reset_ping_timer(ws)

    def on_message(ws, message):
        # Reset pong timeout count on any message
        nonlocal pong_timeout_count
        pong_timeout_count = 0
        
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
                process_trade_message("gateio", data, db_session, bot_config.exchange_api_key.id)
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

def start_bybit_websocket(
    exchange_instance,
    symbol: str,
    bot_config_id: int,
    amount: float,
    step_size: float,
    tick_size: float,
    min_notional: float,
    registry: dict,                   # <── self.websocket_connections
    sl_buffer_percent: float = 2.0,
    sell_rebound_percent: float = 1.5,
    auto_reconnect: bool = True,
    db_session=None
):
    """
    Opens a single, self healing Bybit Spot order stream and stores it in *registry*.
    Re uses the same key «(exchange_id, symbol)».
    """
    # ── 1. fetch API creds ──────────────────────────────────────────────────────
    session = db_session or SessionLocal()
    bot_cfg = (
        session.query(models.ExchangeBotConfig)
        .filter(models.ExchangeBotConfig.id == bot_config_id)
        .first()
    )
    if not (bot_cfg and bot_cfg.exchange_api_key):
        logger.error("❌ No API key found for this bot_config_id")
        session.close()
        return None

    api_key     = bot_cfg.exchange_api_key.api_key
    api_secret  = bot_cfg.exchange_api_key.api_secret
    session.close()

    ws_url  = "wss://stream.bybit.com/v5/private"
    key     = (exchange_instance.id, symbol)          # registry key
    by_sym  = symbol.replace("/", "")                 # e.g. DOGE/USDC → DOGEUSDC

    # Flag to track explicit closure
    is_closing = {"value": False}

    # ── 2. inner helpers ────────────────────────────────────────────────────────
    def _sig(secret, expires):  # sign the auth payload
        payload = f"GET/realtime{expires}"
        return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()

    # ── 3. websocket callbacks ──────────────────────────────────────────────────
    def on_open(ws):
        logger.info("🚀 WS open – authenticating & subscribing")
        expires = int((time.time() + 10) * 1000)
        ws.send(json.dumps({
            "req_id": "10001",
            "op": "auth",
            "args": [api_key, expires, _sig(api_secret, expires)]
        }))
        ws.send(json.dumps({"op": "subscribe", "args": ["order"]}))
        
        # Start ping thread
        def ping_thread():
            while True:
                try:
                    if ws.sock and ws.sock.connected and not is_closing["value"]:
                        ws.send(json.dumps({"op": "ping"}))
                    time.sleep(20)  # Send ping every 20 seconds
                except Exception as e:
                    logger.error(f"Error in ping thread: {e}")
                    break
                except:
                    break
        
        ws.ping_thread = threading.Thread(target=ping_thread, daemon=True)
        ws.ping_thread.start()

    def on_message(ws, raw):
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            logger.error("⚠️  bad JSON")
            return

        # Handle pong response
        if msg.get("op") == "pong":
            logger.debug("Received pong from Bybit")
            return

        # auth/sub ack
        if msg.get("op") in {"auth", "subscribe"}:
            success = msg.get("success", False)
            logger.info("✅ %s %s", msg["op"], "ok" if success else "fail")
            return

        data = (msg.get("data") or [])
        if not data:
            return

        order = data[0]
        if order.get("symbol") != by_sym or order.get("orderStatus") != "Filled":
            return

        # price fallback chain
        price = next(
            (
                float(v) for v in (
                    order.get("price"), order.get("avgPrice"), order.get("lastPriceOnCreated"), "0"
                ) if v and v != "0"
            ),
            0.0
        )

        logger.info("✅ order filled %s @ %.10g", by_sym, price)

        try:
            process_order_update(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent, price
            )
        except Exception as e:
            logger.exception("❌ process_order_update failed: %s", e)

        # trade stream is separate; guard the call
        if msg.get("topic") == "trade":
            try:
                process_trade_message("bybit", msg, db_session, bot_cfg.exchange_api_key.id)
            except Exception as e:
                logger.exception("❌ trade handler failed: %s", e)

    def on_error(ws, err):
        logger.error("🚨 WS error: %s", err)
        # Don't close here, let on_close handle reconnection

    def on_close(ws, code, msg):
        logger.warning("❌ WS closed (%s – %s)", code, msg)
        
        # Stop ping thread if it exists
        if hasattr(ws, 'ping_thread') and ws.ping_thread is not None:
            try:
                if ws.ping_thread.is_alive():
                    ws.ping_thread = None
            except Exception as e:
                logger.warning(f"Error checking ping thread: {e}")
                ws.ping_thread = None

        # has already been removed, so this is a no-op
        registry.pop(key, None)

        # Only reconnect if auto_reconnect is True AND not explicitly closed
        # Check both the code (1000 = normal closure) and our explicit close flag
        if auto_reconnect and code != 1000 and not is_closing["value"]:
            def _reconnect():
                try:
                    # Don't attempt to reconnect if we've explicitly closed
                    if is_closing["value"]:
                        logger.info("Reconnection canceled - WebSocket was explicitly closed")
                        return
                        
                    logger.info("⭮ reconnecting %s in 5s", key)
                    new_ws = build_ws()
                    registry[key] = new_ws
                    threading.Thread(
                        target=lambda: new_ws.run_forever(
                            ping_interval=20,
                            ping_timeout=10,
                            skip_utf8_validation=True
                        ),
                        daemon=True
                    ).start()
                except Exception as e:
                    logger.error(f"Failed to reconnect: {e}")
                    # Try again in 5 seconds if not explicitly closed
                    if not is_closing["value"]:
                        threading.Timer(5, _reconnect).start()
        
            # Schedule reconnection
            threading.Timer(5, _reconnect).start()
        else:
            logger.info("WebSocket closed explicitly or auto_reconnect disabled - not reconnecting")
            # Only call close_and_sell_all if this wasn't an explicit closure through our API
            if not is_closing["value"]:
                close_and_sell_all(exchange_instance, symbol)

    # ── 4. builder so we can reuse in reconnect ─────────────────────────────────
    def build_ws():
        return websocket.WebSocketApp(
            ws_url,
            on_open    = on_open,
            on_message = on_message,
            on_error   = on_error,
            on_close   = on_close
        )

    # ── 5. launch ───────────────────────────────────────────────────────────────
    ws_app = build_ws()
    
    # Add a close method that marks the websocket as explicitly closing to prevent reconnection
    def close_socket():
        try:
            # Set the flag to prevent reconnection
            is_closing["value"] = True
            logger.info(f"Explicitly closing WebSocket for {symbol}")
            
            # First call close_and_sell_all to close positions
            try:
                logger.info(f"Closing all positions for {symbol}")
                close_and_sell_all(exchange_instance, symbol)
            except Exception as e:
                logger.error(f"Error during close_and_sell_all: {e}")
            
            # Stop ping thread if it exists
            if hasattr(ws_app, 'ping_thread') and ws_app.ping_thread is not None:
                try:
                    if ws_app.ping_thread.is_alive():
                        ws_app.ping_thread = None
                except Exception as e:
                    logger.warning(f"Error stopping ping thread: {e}")
                    ws_app.ping_thread = None
            
            # Force close the connection
            if hasattr(ws_app, "sock") and ws_app.sock is not None:
                try:
                    ws_app.sock.close()
                except Exception as e:
                    logger.error(f"Error closing socket: {e}")
            
            # Close websocket
            ws_app.close()
            
            # Remove from registry directly to prevent any potential reconnection attempts
            if key in registry:
                registry.pop(key)
                
            logger.info(f"Successfully closed WebSocket for {symbol}")
        except Exception as e:
            logger.error(f"Error during explicit WebSocket closure: {e}")
            # Even on error, make sure it's removed from registry
            if key in registry:
                registry.pop(key)
    
    # Attach our custom close method to the websocket object
    ws_app.close_socket = close_socket
    
    # Store in registry
    registry[key] = ws_app

    threading.Thread(
        target=lambda: ws_app.run_forever(
            ping_interval=20,
            ping_timeout=10,
            skip_utf8_validation=True
        ),
        daemon=True
    ).start()

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

        # Safely parse JSON with error handling
        try:
            tp_levels = json.loads(bot_config.tp_levels_json or '[]')
            sl_levels = json.loads(bot_config.sl_levels_json or '[]')
        except json.JSONDecodeError:
            logger.error(f"❌ Error parsing TP/SL levels JSON for bot {bot_config_id}")
            return
            
        # Add logging to help debug
        logger.info(f"{exchange_instance.id}: Checking stored TP: {tp_levels}, stored SL: {sl_levels}")

        # Check balance before processing orders
        base_asset, quote_asset = symbol.split('/')
        balance = exchange_instance.fetch_balance()
        quote_balance = balance.get(quote_asset, {}).get('free', 0)
        base_balance = balance.get(base_asset, {}).get('free', 0)
        
        # Process TP orders
        for i in range(len(tp_levels)):
            if current_price >= tp_levels[i]:
                triggered_tp = tp_levels.pop(i)
                bot_config.tp_levels_json = json.dumps(tp_levels)
                session.commit()
                logger.info(f"🎯 Price {current_price} hit TP {triggered_tp}")

                # If we have no TP left, it means that was the last TP
                if len(tp_levels) == 0:
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

                # Place new SL order only if we have enough quote balance
                if quote_balance >= amount:
                    new_sl_price = round_price(triggered_tp * (1 - sl_buffer_percent / 100), tick_size)

                    # Remove the oldest (lowest) SL level
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

                    # Place new SL order
                    threading.Timer(
                        0.5,
                        place_limit_buys,
                        args=(exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional)
                    ).start()

                    # Add to SL levels
                    sl_levels.append(new_sl_price)
                    sl_levels.sort(reverse=True)  # Sort in descending order
                    bot_config.sl_levels_json = json.dumps(sl_levels)
                    session.commit()
                else:
                    logger.warning(f"Insufficient {quote_asset} balance ({quote_balance}) to place new SL order")
                break

        # Process SL orders
        for sl_price in sl_levels[:]:  # Make a copy of the list to safely modify during iteration
            if current_price <= sl_price:
                sl_levels.remove(sl_price)  # Remove this triggered SL
                
                new_sl_price = round_price(sl_price * (1 - sl_buffer_percent / 100), tick_size)
                new_sell_price = round_price(sl_price * (1 + sell_rebound_percent / 100), tick_size)
                
                # Make sure we have enough balance before placing orders
                if base_balance <= step_size:
                    logger.warning(f"Insufficient {base_asset} balance ({base_balance}) to place sell order")
                else:
                    # Place the sell order only if we have balance
                    threading.Timer(
                        0.5,
                        place_limit_sell,
                        args=(exchange_instance, symbol, base_balance, new_sell_price, step_size)
                    ).start()
                    
                    # Add to TP levels
                    tp_levels.append(new_sell_price)
                    tp_levels.sort(reverse=True)  # Sort in descending order
                
                # Place the buy order only if we have enough quote balance
                if quote_balance >= amount:
                    threading.Timer(
                        0.5,
                        place_limit_buys,
                        args=(exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional)
                    ).start()
                    
                    # Add to SL levels
                    sl_levels.append(new_sl_price)
                    sl_levels.sort(reverse=True)  # Sort in descending order
                else:
                    logger.warning(f"Insufficient {quote_asset} balance ({quote_balance}) to place new SL order")

                # Update config with new arrays
                bot_config.tp_levels_json = json.dumps(tp_levels)
                bot_config.sl_levels_json = json.dumps(sl_levels)
                session.commit()
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
