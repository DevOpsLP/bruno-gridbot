import websocket  # pip install websocket-client
import threading
import logging
import json
import math
import time
import requests
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
    logger.info(f"Market buy executed: {order_size} {base_asset} @ {current_price}")

    # The "intended" prices
    intended_tp = round_price(current_price * (1 + tp_percent / 100), tick_size)
    intended_sls = [
        round_price(current_price * (1 - sl_percent / 100) ** (i + 1), tick_size)
        for i in range(3)
    ]
    
    # Place TP & SL orders, then store them
    actual_tp_price = place_limit_sell(exchange, symbol, order_size, intended_tp, step_size)
    actual_sl_prices = place_limit_buys(exchange, symbol, amount, intended_sls, step_size, min_notional)

    bot_config.tp_levels_json = json.dumps([actual_tp_price])
    bot_config.sl_levels_json = json.dumps(actual_sl_prices)
    logger.info(f"Started Grid: TP Levels: {bot_config.tp_levels_json} / Stop Loss Levels: {bot_config.sl_levels_json} ")
    db_session.commit()


def place_limit_sell(exchange, symbol, amount, price, step_size):
    """
    Place a single limit sell at 'price'. Return the final float price from the exchange's response.
    """
    amount = Decimal(str(amount)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision
    price = Decimal(str(price))  # Convert price to Decimal

    try:
        order = exchange.create_limit_sell_order(symbol, float(amount), float(price))  # Convert back to float
        final_price = float(order['price'])
        logger.info(f"Limit sell placed: {amount} @ {final_price}")
        return final_price
    except Exception as e:
        logger.error(f"Limit sell error {amount} @ {price}: {repr(e)}")
        return float(price)  # Fallback
    
    
def place_limit_buys(exchange, symbol, total_usdt, prices, step_size, min_notional):
    """
    Place one limit buy for each price in `prices`, each using the full `total_usdt`.
    Returns a list of final float prices from the exchange's responses.
    """
    final_prices = []
    for p in prices:
        p = Decimal(str(p))  # Ensure price is also a Decimal
        amount = Decimal(total_usdt) / p  # Convert total_usdt to Decimal before division
        amount = amount.quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)  # Fix precision

        if not min_notional or (amount * p) >= Decimal(str(min_notional)):  # Convert min_notional to Decimal
            try:
                order = exchange.create_limit_buy_order(symbol, float(amount), float(p))  # Convert back to float
                final_price = float(order['price'])
                logger.info(f"Limit buy placed: {amount} @ {final_price}")
                final_prices.append(final_price)
            except Exception as e:
                logger.error(f"Limit buy error @ {p}: {repr(e)}")
                final_prices.append(float(p))  # Convert Decimal back to float for consistency
        else:
            logger.warning(f"Skipping SL @ {p} due to min_notional check.")
            final_prices.append(float(p))

    return final_prices
def get_listen_key(api_key):
    """Fetch listenKey from Binance User Data Stream API."""
    headers = {"X-MBX-APIKEY": api_key}
    response = requests.post(f"https://api.binance.com/api/v3/userDataStream", headers=headers)
    data = response.json()

    if "listenKey" in data:
        return data["listenKey"]
    else:
        raise Exception(f"Error fetching listenKey: {data}")

def start_binance_websocket(exchange_instance, symbol, bot_config_id, amount,
                            step_size, tick_size, min_notional, 
                            sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                            auto_reconnect=True, db_session=None):
    """
    Starts a Binance WebSocket connection for user data stream.
    """
    
    # 🏆 Fetch bot config (Includes relationship with ExchangeAPIKey)
    bot_config = crud.get_bot_config_by_exchange_symbol(db_session, exchange_instance.id, symbol)

    if not bot_config or not bot_config.exchange_api_key:
        logger.error(f"❌ No API key found for exchange {exchange_instance.id}. Please create an API key first.")
        return None

    # ✅ Directly access `api_key` from the relationship
    api_key = bot_config.exchange_api_key.api_key

    # 🔥 Get listenKey manually
    listen_key = get_listen_key(api_key)
    ws_url = f"wss://stream.binance.com:9443/ws/{listen_key}"

    def on_open(ws):
        logger.info(f"✅ WebSocket connected to {ws_url}")

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ WebSocket closed: {close_status_code}, {close_msg}")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
        else:
            logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure; not attempting to reconnect.")
            return
        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")
        threading.Timer(
            reconnect_delay,
            lambda: start_binance_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=auto_reconnect
            )
        ).start()

    def on_error(ws, error):
        logger.error(f"🚨 WebSocket error: {error}")
        # Trigger closure if auto-reconnect is enabled
        if getattr(ws, "auto_reconnect", True):
            ws.close()


    def on_message(ws, message):
        try:
            data = json.loads(message)

            # 🔄 Respond to Binance `ping` messages with a `pong`
            if "ping" in data:
                ws.send(json.dumps({"pong": data["ping"]}))  # 🔁 Send back the same payload
                return  # ⛔ No need to process further

            # 🔍 FILTER: Only process "executionReport" events with "FILLED" status
            if not (data.get("e") == "executionReport" and data.get("X") == "FILLED"):
                return  # ⛔ Skip if it's not the event we need

            # ✅ Use "L" as current price
            symbol_price = float(data["L"])
            current_price = symbol_price

            session = SessionLocal()
            bot_config = session.query(models.ExchangeBotConfig)\
                                .filter(models.ExchangeBotConfig.id == bot_config_id)\
                                .first()
            if not bot_config:
                logger.error(f"⚠️ Bot config with ID {bot_config_id} not found.")
                return

            session.refresh(bot_config)
            tp_levels = json.loads(bot_config.tp_levels_json)
            sl_levels = json.loads(bot_config.sl_levels_json)
            
            logger.info(f"Current Price: {current_price} | Current TPs: {tp_levels} | Current Stop Loss: {sl_levels}")

            for i in range(len(tp_levels)):  
                if current_price >= tp_levels[i]:  
                    triggered_tp = tp_levels.pop(i)  # ✅ Remove the TP hit
                    bot_config.tp_levels_json = json.dumps(tp_levels)
                    session.commit()
                    logger.info(f"🎯 Price {current_price} hit TP {triggered_tp}")

                    if i == 0:  
                        logger.info("All TPs filled! -> Resetting grid after delay.")
                        try:
                            open_orders = exchange_instance.fetch_open_orders(symbol)
                            for order in open_orders:
                                exchange_instance.cancel_order(order['id'], symbol)
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

                    else:  
                        new_sl_price = round_price(triggered_tp * (1 - sl_buffer_percent / 100), tick_size)

                        if sl_levels:
                            last_sl = min(sl_levels)
                            try:
                                open_orders = exchange_instance.fetch_open_orders(symbol)
                                for order in open_orders:
                                    if order['price'] == last_sl:
                                        exchange_instance.cancel_order(order['id'], symbol)
                                        break  
                            except Exception as e:
                                logger.error(f"❌ Error cancelling SL orders: {e}")

                            sl_levels.remove(last_sl)

                        sl_levels.insert(0, new_sl_price)
                        sl_levels.sort(reverse=True)

                        threading.Timer(0.5, place_limit_buys, args=(
                            exchange_instance, symbol, amount, [new_sl_price], tick_size, min_notional
                        )).start()

                        bot_config.sl_levels_json = json.dumps(sl_levels)
                        session.commit()

                    break  

            for sl_price in sl_levels:
                if current_price <= sl_price:
                    last_sl = min(sl_levels)
                    new_sl_price = round_price(last_sl * (1 - sl_buffer_percent / 100), tick_size)
                    new_sell_price = round_price(sl_price * (1 + sell_rebound_percent / 100), tick_size)

                    base_asset, _ = symbol.split('/')
                    balance = exchange_instance.fetch_balance()
                    base_balance = balance.get(base_asset, {}).get('free')

                    threading.Timer(0.5, place_limit_buys, args=(
                        exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional
                    )).start()

                    threading.Timer(0.5, place_limit_sell, args=(
                        exchange_instance, symbol, base_balance, new_sell_price, step_size
                    )).start()

                    sl_levels.remove(sl_price)
                    sl_levels.append(new_sl_price)
                    sl_levels.sort(reverse=True)
                    bot_config.sl_levels_json = json.dumps(sl_levels)

                    tp_levels = json.loads(bot_config.tp_levels_json)
                    tp_levels.append(new_sell_price)
                    tp_levels.sort(reverse=True)  
                    bot_config.tp_levels_json = json.dumps(tp_levels)

                    session.commit()
                    break

        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {e}")
        finally:
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

    ws = websocket.WebSocketApp(ws_url,
                                on_open=on_open,
                                on_close=on_close,
                                on_error=on_error,
                                on_message=on_message)
    ws.auto_reconnect = auto_reconnect
    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()
    logger.info(f"🚀 Started Binance WebSocket for {symbol}. Listening for price movements...")
    return ws

def start_bitmart_websocket(exchange_instance, symbol, bot_config_id, amount,
                            step_size, tick_size, min_notional, 
                            sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                            auto_reconnect=True):
    ws_url = "wss://ws-manager-compress.bitmart.com/api?protocol=1.1"
    channel_symbol = symbol.replace("/", "_")

    def on_open(ws):
        logger.info(f"✅ BitMart WebSocket connected to {ws_url}")
        subscription_message = json.dumps({
            "op": "subscribe",
            "args": [f"spot/ticker:{channel_symbol}"]
        })
        ws.send(subscription_message)
        logger.info(f"Subscribed to spot/ticker channel for {channel_symbol}")

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ BitMart WebSocket closed: {close_status_code}, {close_msg}")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
        else:
            logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure; not attempting to reconnect.")
            return
        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")
        threading.Timer(
            reconnect_delay,
            lambda: start_bitmart_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=auto_reconnect
            )
        ).start()

    def on_error(ws, error):
        logger.error(f"🚨 BitMart WebSocket error: {error}")
        # If auto-reconnect is enabled, force closure to trigger on_close
        if getattr(ws, "auto_reconnect", True):
            ws.close()

    def on_message(ws, message):
        session = None
        try:
            data = json.loads(message)
            if "data" in data and isinstance(data["data"], list) and data["data"]:
                ticker = data["data"][0]
                current_price = float(ticker.get("last_price", ticker.get("ask_px", 0)))
            else:
                return

            session = SessionLocal()
            bot_config = session.query(models.ExchangeBotConfig)\
                                .filter(models.ExchangeBotConfig.id == bot_config_id)\
                                .first()
            if not bot_config:
                logger.error(f"⚠️ Bot config with ID {bot_config_id} not found.")
                return

            tp_levels = json.loads(bot_config.tp_levels_json)
            sl_levels = json.loads(bot_config.sl_levels_json)
            
            for i in range(len(tp_levels)):  
                    if current_price >= tp_levels[i]:  
                        logger.info(f"GateIO TP Level: {tp_levels}")
                        triggered_tp = tp_levels.pop(i)  # ✅ Remove the TP hit
                        bot_config.tp_levels_json = json.dumps(tp_levels)
                        logger.info(f"GateIO Level dumped, current TP Levels: {bot_config.tp_levels_json}")
                        session.commit()
                        logger.info(f"🎯 Price {current_price} hit TP {triggered_tp}")

                        # ✅ If `i == 0`, we hit the **highest** TP -> reset the grid
                        if i == 0:  
                            logger.info("All TPs filled! -> Resetting grid after delay.")
                            try:
                                open_orders = exchange_instance.fetch_open_orders(symbol)
                                for order in open_orders:
                                    exchange_instance.cancel_order(order['id'], symbol)
                                    logger.info(f"🛑 Cancelled order {order['id']}")
                            except Exception as e:
                                logger.error(f"❌ Error cancelling orders: {e}")
                            
                            initialize_orders, (
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
                            return  # ✅ Stop further TP processing (Grid Reset)

                        else:  
                            # ✅ Place a new SL based on the TP hit
                            new_sl_price = round_price(triggered_tp * (1 - sl_buffer_percent / 100), tick_size)

                            if sl_levels:
                                last_sl = min(sl_levels)  # Get the lowest SL
                                try:
                                    open_orders = exchange_instance.fetch_open_orders(symbol)
                                    for order in open_orders:
                                        if order['price'] == last_sl:
                                            exchange_instance.cancel_order(order['id'], symbol)
                                            logger.info(f"🛑 Cancelled lowest SL order {order['id']} at {last_sl}")
                                            break  
                                except Exception as e:
                                    logger.error(f"❌ Error cancelling SL orders: {e}")

                                # ✅ Remove the old SL from the array
                                sl_levels.remove(last_sl)

                            # ✅ Add new SL at position 0 (since it's the highest SL now)
                            sl_levels.insert(0, new_sl_price)

                            # ✅ Place new limit buy order at new SL level
                            threading.Timer(0.5, place_limit_buys, args=(
                                exchange_instance, symbol, amount, [new_sl_price], tick_size, min_notional
                            )).start()

                            logger.info(f"📈 New SL placed at {new_sl_price}")

                            # ✅ Update SL levels in bot config
                            bot_config.sl_levels_json = json.dumps(sl_levels)
                            session.commit()

                        break  # ✅ Stop after processing the first TP hit

            for sl_price in sl_levels:
                if current_price <= sl_price:
                    logger.info(f"⚠️ Price {current_price} hit SL {sl_price} -> Placing new SL & Sell orders after delay.")
                    last_sl = min(sl_levels)
                    new_sl_price = round_price(last_sl * (1 - sl_buffer_percent / 100), tick_size)
                    new_sell_price = round_price(sl_price * (1 + sell_rebound_percent / 100), tick_size)
                    logger.info(f"🔁 New SL @ {new_sl_price} | New Sell @ {new_sell_price}")
                    base_asset, _ = symbol.split('/')
                    balance = exchange_instance.fetch_balance()
                    base_balance = balance.get(base_asset, {}).get('free')
                    threading.Timer(0.5, place_limit_buys, args=(
                        exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional
                    )).start()
                    threading.Timer(0.5, place_limit_sell, args=(
                        exchange_instance, symbol, base_balance, new_sell_price, step_size
                    )).start()
                    sl_levels.remove(sl_price)
                    sl_levels.append(new_sl_price)
                    sl_levels.sort(reverse=True)
                    bot_config.sl_levels_json = json.dumps(sl_levels)
                    
                    # ★★★ Add your new sell price to TP array so it's tracked in on_message
                    tp_levels = json.loads(bot_config.tp_levels_json)
                    tp_levels.append(new_sell_price)
                    # If your code expects TPs in descending order, do this:
                    tp_levels.sort(reverse=True)  
                    # If it expects ascending, remove "reverse=True".
                    bot_config.tp_levels_json = json.dumps(tp_levels)

                    session.commit()
                    break


        except Exception as e:
            logger.error(f"❌ Error processing BitMart WebSocket message: {e}")
        finally:
            if session is not None:
                session.close()

    def close_and_sell_all(exchange_instance, symbol):
        try:
            open_orders = exchange_instance.fetch_open_orders(symbol)
            for order in open_orders:
                exchange_instance.cancel_order(order['id'], symbol)
                logger.info(f"🛑 Cancelled order {order['id']}")
            base_asset, _ = symbol.split('/')
            balance = exchange_instance.fetch_balance()
            base_balance = balance.get(base_asset, {}).get('free')
            if base_balance > 0:
                sell_order = exchange_instance.create_market_sell_order(symbol, base_balance)
                logger.info(f"💰 Sold {base_balance} {base_asset} for USDT")
            else:
                logger.info(f"⚠️ No {base_asset} balance to sell.")
        except Exception as e:
            logger.error(f"❌ Error during close_and_sell_all: {e}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_close=on_close,
        on_error=on_error,
        on_message=on_message
    )
    ws.auto_reconnect = auto_reconnect
    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()
    logger.info(f"🚀 Started BitMart WebSocket for {symbol}. Listening for price movements...")
    return ws

def start_gateio_websocket(exchange_instance, symbol, bot_config_id, amount,
                           step_size, tick_size, min_notional, 
                           sl_buffer_percent=2.0, sell_rebound_percent=1.5,
                           auto_reconnect=True):
    ws_url = "wss://api.gateio.ws/ws/v4/"
    channel_symbol = symbol.replace("/", "_")

    def on_open(ws):
        logger.info(f"✅ Gate.io WebSocket connected to {ws_url}")
        subscription_message = json.dumps({
            "time": int(time.time()),
            "channel": "spot.tickers",
            "event": "subscribe",
            "payload": [channel_symbol]
        })
        ws.send(subscription_message)
        logger.info(f"Subscribed to spot/ticker channel for {channel_symbol}")

    def on_close(ws, close_status_code, close_msg):
        logger.info(f"❌ Gate.io WebSocket closed: {close_status_code}, {close_msg}")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure detected; closing orders.")
            close_and_sell_all(exchange_instance, symbol)
        else:
            logger.info("Connection lost but auto-reconnect is enabled; preserving orders.")
        if not getattr(ws, "auto_reconnect", True):
            logger.info("Forced closure; not attempting to reconnect.")
            return
        reconnect_delay = 5  # seconds
        logger.info(f"Attempting to reconnect in {reconnect_delay} seconds...")
        threading.Timer(
            reconnect_delay,
            lambda: start_gateio_websocket(
                exchange_instance, symbol, bot_config_id, amount,
                step_size, tick_size, min_notional,
                sl_buffer_percent, sell_rebound_percent,
                auto_reconnect=auto_reconnect
            )
        ).start()

    def on_error(ws, error):
        logger.error(f"🚨 Gate.io WebSocket error: {error}")
        # If auto-reconnect is enabled, force closure to trigger on_close
        if getattr(ws, "auto_reconnect", True):
            ws.close()
            
    def on_message(ws, message):
        session = None
        try:
            data = json.loads(message)

            # ✅ Ignore subscription confirmation messages
            if "event" in data and data["event"] == "subscribe":
                logger.info(f"✅ Subscription confirmed for {data.get('payload', [])}")
                return
            
            # ✅ Ensure the message is a price update
            if "result" not in data or "last" not in data["result"]:
                logger.info(f"🔍 Ignored message: {data}")  # Debugging
                return
            
            ticker = data["result"]
            current_price = float(ticker["last"])

            session = SessionLocal()
            bot_config = session.query(models.ExchangeBotConfig)\
                                .filter(models.ExchangeBotConfig.id == bot_config_id)\
                                .first()
            if not bot_config:
                logger.error(f"⚠️ Bot config with ID {bot_config_id} not found.")
                return

            tp_levels = json.loads(bot_config.tp_levels_json)
            sl_levels = json.loads(bot_config.sl_levels_json)
            
            for i in range(len(tp_levels)):  
                    if current_price >= tp_levels[i]:  
                        logger.info(f"GateIO TP Level: {tp_levels}")
                        triggered_tp = tp_levels.pop(i)  # ✅ Remove the TP hit
                        bot_config.tp_levels_json = json.dumps(tp_levels)
                        logger.info(f"GateIO Level dumped, current TP Levels: {bot_config.tp_levels_json}")
                        session.commit()
                        logger.info(f"🎯 Price {current_price} hit TP {triggered_tp}")

                        # ✅ If `i == 0`, we hit the **highest** TP -> reset the grid
                        if i == 0:  
                            logger.info("All TPs filled! -> Resetting grid after delay.")
                            try:
                                open_orders = exchange_instance.fetch_open_orders(symbol)
                                for order in open_orders:
                                    exchange_instance.cancel_order(order['id'], symbol)
                                    logger.info(f"🛑 Cancelled order {order['id']}")
                            except Exception as e:
                                logger.error(f"❌ Error cancelling orders: {e}")
                            
                            initialize_orders, (
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
                            return  # ✅ Stop further TP processing (Grid Reset)

                        else:  
                            # ✅ Place a new SL based on the TP hit
                            new_sl_price = round_price(triggered_tp * (1 - sl_buffer_percent / 100), tick_size)

                            if sl_levels:
                                last_sl = min(sl_levels)  # Get the lowest SL
                                try:
                                    open_orders = exchange_instance.fetch_open_orders(symbol)
                                    for order in open_orders:
                                        if order['price'] == last_sl:
                                            exchange_instance.cancel_order(order['id'], symbol)
                                            logger.info(f"🛑 Cancelled lowest SL order {order['id']} at {last_sl}")
                                            break  
                                except Exception as e:
                                    logger.error(f"❌ Error cancelling SL orders: {e}")

                                # ✅ Remove the old SL from the array
                                sl_levels.remove(last_sl)

                            # ✅ Add new SL at position 0 (since it's the highest SL now)
                            sl_levels.insert(0, new_sl_price)

                            # ✅ Place new limit buy order at new SL level
                            threading.Timer(0.5, place_limit_buys, args=(
                                exchange_instance, symbol, amount, [new_sl_price], tick_size, min_notional
                            )).start()

                            logger.info(f"📈 New SL placed at {new_sl_price}")

                            # ✅ Update SL levels in bot config
                            bot_config.sl_levels_json = json.dumps(sl_levels)
                            session.commit()

                        break  # ✅ Stop after processing the first TP hit


            for sl_price in sl_levels:
                if current_price <= sl_price:
                    logger.info(f"⚠️ Price {current_price} hit SL {sl_price} -> Placing new SL & Sell orders after delay.")
                    last_sl = min(sl_levels)
                    new_sl_price = round_price(last_sl * (1 - sl_buffer_percent / 100), tick_size)
                    new_sell_price = round_price(sl_price * (1 + sell_rebound_percent / 100), tick_size)
                    logger.info(f"🔁 New SL @ {new_sl_price} | New Sell @ {new_sell_price}")
                    base_asset, _ = symbol.split('/')
                    balance = exchange_instance.fetch_balance()
                    base_balance = balance.get(base_asset, {}).get('free')
                    threading.Timer(0.5, place_limit_buys, args=(
                        exchange_instance, symbol, amount, [new_sl_price], step_size, min_notional
                    )).start()
                    threading.Timer(0.5, place_limit_sell, args=(
                        exchange_instance, symbol, base_balance, new_sell_price, step_size
                    )).start()
                    sl_levels.remove(sl_price)
                    sl_levels.append(new_sl_price)
                    sl_levels.sort(reverse=True)
                    bot_config.sl_levels_json = json.dumps(sl_levels)
                    
                    # ★★★ Add your new sell price to TP array so it's tracked in on_message
                    tp_levels = json.loads(bot_config.tp_levels_json)
                    tp_levels.append(new_sell_price)
                    # If your code expects TPs in descending order, do this:
                    tp_levels.sort(reverse=True)  
                    # If it expects ascending, remove "reverse=True".
                    bot_config.tp_levels_json = json.dumps(tp_levels)

                    session.commit()
                    break


        except Exception as e:
            logger.error(f"❌ Error processing Gate.io WebSocket message: {e}")
        finally:
            if session is not None:
                session.close()

    def close_and_sell_all(exchange_instance, symbol):
        try:
            open_orders = exchange_instance.fetch_open_orders(symbol)
            for order in open_orders:
                exchange_instance.cancel_order(order['id'], symbol)
                logger.info(f"🛑 Cancelled order {order['id']}")
            base_asset, _ = symbol.split('/')
            balance = exchange_instance.fetch_balance()
            base_balance = balance.get(base_asset, {}).get('free')
            if base_balance > 0:
                sell_order = exchange_instance.create_market_sell_order(symbol, base_balance)
                logger.info(f"💰 Sold {base_balance} {base_asset} for USDT")
            else:
                logger.info(f"⚠️ No {base_asset} balance to sell.")
        except Exception as e:
            logger.error(f"❌ Error during close_and_sell_all: {e}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_close=on_close,
        on_error=on_error,
        on_message=on_message
    )
    ws.auto_reconnect = auto_reconnect
    wst = threading.Thread(target=ws.run_forever, daemon=True)
    wst.start()
    logger.info(f"🚀 Started Gate.io WebSocket for {symbol}. Listening for price movements...")
    return ws

###