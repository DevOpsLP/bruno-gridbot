# src/utils/trade_normalizers.py

from sqlalchemy.orm import Session
from src.database.schemas import TradeRecordBase
from src.database import crud  # Import your CRUD functions

# Helper: Normalize symbol strings (e.g., "INJ/USDT", "INJ_USDT" become "INJUSDT")
def normalize_symbol(symbol: str) -> str:
    return symbol.replace("/", "").replace("_", "").upper()

# Normalizer for Binance messages
def normalize_binance(msg: dict, exchange_api_key_id: int) -> TradeRecordBase:
    return TradeRecordBase(
        exchange_api_key_id=exchange_api_key_id,
        symbol_id=normalize_symbol(msg["s"]),
        order_id=msg["c"],
        trade_id=str(msg["t"]),
        side=msg["S"].lower(),
        order_type=msg["o"].lower(),
        amount=float(msg["l"]),
        price=float(msg["L"]),
        fee=float(msg.get("n", 0)),
        fee_currency=msg.get("N"),
        cost=float(msg["l"]) * float(msg["L"]),
        pnl=0.0
    )

# Normalizer for Gate.io messages
def normalize_gateio(msg: dict, exchange_api_key_id: int) -> TradeRecordBase:
    data = msg["result"][0]
    return TradeRecordBase(
        exchange_api_key_id=exchange_api_key_id,
        symbol_id=normalize_symbol(data["currency_pair"]),
        order_id=data["order_id"],
        trade_id=str(data["id"]),
        side=data["side"].lower(),
        order_type="limit",  # Assuming limit orders for now
        amount=float(data["amount"]),
        price=float(data["price"]),
        fee=float(data["fee"]),
        fee_currency=data["fee_currency"],
        cost=float(data["amount"]) * float(data["price"]),
        pnl=0.0
    )

def normalize_bybit(msg: dict, exchange_api_key_id: int) -> TradeRecordBase:
    return TradeRecordBase(
        exchange_api_key_id=exchange_api_key_id,
        symbol=normalize_symbol(msg["symbol"]),  # Change here from symbol_id to symbol
        order_id=msg["orderId"],
        trade_id=None,  # Adjust if available
        side=msg["side"].lower(),
        order_type=msg["orderType"].lower(),
        amount=float(msg["cumExecQty"]),
        price=float(msg["avgPrice"]),
        fee=float(msg["cumExecFee"]),
        fee_currency=msg.get("feeCurrency", "USDT"),
        cost=float(msg["cumExecValue"]),
        pnl=0.0
    )

# Normalizer for Bitmart messages
def normalize_bitmart(msg: dict, exchange_api_key_id: int) -> TradeRecordBase:
    data = msg["data"][0]
    return TradeRecordBase(
        exchange_api_key_id=exchange_api_key_id,
        symbol_id=normalize_symbol(data["symbol"]),
        order_id=data["order_id"],
        trade_id=data["detail_id"],
        side=data["side"].lower(),
        order_type="limit",  # Assuming limit orders
        amount=float(data["filled_size"]),
        price=float(data["last_fill_price"]),
        fee=float(data["dealFee"]),
        fee_currency=data.get("fee_currency", data.get("feeCurrency")),
        cost=float(data["filled_notional"]) if data["filled_notional"] else float(data["price"]) * float(data["filled_size"]),
        pnl=0.0
    )

# Dispatcher to normalize message based on exchange name
def normalize_trade_message(exchange: str, msg: dict, exchange_api_key_id: int) -> TradeRecordBase:
    exchange = exchange.lower()
    if exchange == "binance":
        return normalize_binance(msg, exchange_api_key_id)
    elif exchange == "gateio":
        return normalize_gateio(msg, exchange_api_key_id)
    elif exchange == "bybit":
        return normalize_bybit(msg, exchange_api_key_id)
    elif exchange == "bitmart":
        return normalize_bitmart(msg, exchange_api_key_id)
    else:
        raise ValueError(f"Exchange '{exchange}' not supported")

# Process a raw message from an exchange and create a trade record
def process_trade_message(exchange: str, raw_msg: dict, db: Session, exchange_api_key_id: int):
    normalized_trade = normalize_trade_message(exchange, raw_msg, exchange_api_key_id)
    return crud.create_trade_record(db, normalized_trade)