import logging
import time
from bitmart.lib.cloud_consts import SPOT_PRIVATE_WS_URL
from bitmart.websocket.spot_socket_client import SpotSocketClient

# ✅ Logging setup
logging.basicConfig(level=logging.INFO)

# ✅ API Credentials
API_KEY = "d7e89c84345ed5f156daaa98f4e2e4329dedda4a"
API_SECRET = "c70d539626cb8c140c599dd184bb86bb97019ae06baebb9abd21551f9ebd1696"
API_MEMO = "bua"

# ✅ Define WebSocket message handler
def message_handler(message):
    logging.info(f"📩 Order Update Received: {message}")

# ✅ Create WebSocket Client (Using Private API)
my_client = SpotSocketClient(
    stream_url=SPOT_PRIVATE_WS_URL,
    on_message=message_handler,
    api_key=API_KEY,
    api_secret_key=API_SECRET,
    api_memo=API_MEMO
)

# ✅ Login
logging.info("🔑 Logging into BitMart WebSocket...")
my_client.login(timeout=5)

# ✅ Subscribe to **ALL ORDER UPDATES**
logging.info("📡 Subscribing to all order updates...")
my_client.subscribe(args="spot/user/orders:ALL_SYMBOLS")

# ✅ Keep running (WebSocket is automatically managed)
while True:
    time.sleep(5)  # Prevents script from exiting
    
    
#     INFO:root:📩 Order Update Received: {'topic': 'spot/user/orders:ALL_SYMBOLS', 'event': 'subscribe'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320462080', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320462080', 'notional': '', 'order_id': '995232205536716288', 'order_mode': 'spot', 'order_state': 'canceled', 'order_type': '0', 'price': '2.7322', 'side': 'buy', 'size': '3.65', 'state': '8', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742320511931'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320523705', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320523705', 'notional': '9.99', 'order_id': '995233239432652288', 'order_mode': 'spot', 'order_state': 'new', 'order_type': '0', 'price': '0', 'side': 'buy', 'size': '0', 'state': '4', 'symbol': 'FIL_USDT', 'type': 'market', 'update_time': '1742320523705'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320523705', 'dealFee': '0.009976384', 'detail_id': '995233239465470470', 'entrust_type': 'NORMAL', 'exec_type': 'T', 'filled_notional': '9.976384', 'filled_size': '3.52', 'last_fill_count': '3.52', 'last_fill_price': '2.8342', 'last_fill_time': '1742320523709', 'margin_trading': '0', 'ms_t': '1742320523705', 'notional': '9.99', 'order_id': '995233239432652288', 'order_mode': 'spot', 'order_state': 'partially_filled', 'order_type': '0', 'price': '0', 'side': 'buy', 'size': '0', 'state': '5', 'symbol': 'FIL_USDT', 'type': 'market', 'update_time': '1742320523709'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320523705', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '9.976384', 'filled_size': '3.52', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320523705', 'notional': '9.99', 'order_id': '995233239432652288', 'order_mode': 'spot', 'order_state': 'partially_canceled', 'order_type': '0', 'price': '0', 'side': 'buy', 'size': '0', 'state': '12', 'symbol': 'FIL_USDT', 'type': 'market', 'update_time': '1742320523710'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320689515', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320689515', 'notional': '9.9792', 'order_id': '995236021262837249', 'order_mode': 'spot', 'order_state': 'new', 'order_type': '0', 'price': '2.835', 'side': 'buy', 'size': '3.52', 'state': '4', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742320689515'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320922848', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320922848', 'notional': '9.98624', 'order_id': '995239935940978176', 'order_mode': 'spot', 'order_state': 'new', 'order_type': '0', 'price': '2.837', 'side': 'buy', 'size': '3.52', 'state': '4', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742320922848'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320689515', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320689515', 'notional': '', 'order_id': '995236021262837249', 'order_mode': 'spot', 'order_state': 'canceled', 'order_type': '0', 'price': '2.835', 'side': 'buy', 'size': '3.52', 'state': '8', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742320931720'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742321045346', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742321045346', 'notional': '9.97542', 'order_id': '995241991116383744', 'order_mode': 'spot', 'order_state': 'new', 'order_type': '0', 'price': '2.842', 'side': 'buy', 'size': '3.51', 'state': '4', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742321045346'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742321045346', 'dealFee': '0.00997542', 'detail_id': '995241993598675456', 'entrust_type': 'NORMAL', 'exec_type': 'M', 'filled_notional': '9.97542', 'filled_size': '3.51', 'last_fill_count': '3.51', 'last_fill_price': '2.842', 'last_fill_time': '1742321045496', 'margin_trading': '0', 'ms_t': '1742321045346', 'notional': '', 'order_id': '995241991116383744', 'order_mode': 'spot', 'order_state': 'filled', 'order_type': '0', 'price': '2.842', 'side': 'buy', 'size': '3.51', 'state': '6', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742321045496'}], 'table': 'spot/user/orders'}
# INFO:root:📩 Order Update Received: {'data': [{'client_order_id': '0', 'create_time': '1742320922848', 'dealFee': '0', 'entrust_type': 'NORMAL', 'filled_notional': '0', 'filled_size': '0', 'last_fill_count': '0', 'last_fill_price': '0', 'last_fill_time': '0', 'margin_trading': '0', 'ms_t': '1742320922848', 'notional': '', 'order_id': '995239935940978176', 'order_mode': 'spot', 'order_state': 'canceled', 'order_type': '0', 'price': '2.837', 'side': 'buy', 'size': '3.52', 'state': '8', 'symbol': 'FIL_USDT', 'type': 'limit', 'update_time': '1742321054946'}], 'table': 'spot/user/orders'}
# ^[^CTraceback (most recent call last):