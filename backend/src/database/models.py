from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class ExchangeAPIKey(Base):
    __tablename__ = "exchange_api_keys"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, index=True)
    api_key = Column(String)
    api_secret = Column(String)
    balance = Column(Float, default=0.0)
    leverage = Column(Float, default=1.0)

class Symbol(Base):
    __tablename__ = "symbols"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True)  # Example: "ETH/USDT"
    
    # models.py (in the same folder as ExchangeAPIKey and Symbol definitions)

class ExchangeBotConfig(Base):
    __tablename__ = "exchange_bot_config"

    id = Column(Integer, primary_key=True, index=True)
    exchange_id = Column(Integer, ForeignKey("exchange_api_keys.id"))
    symbol_id = Column(Integer, ForeignKey("symbols.id"))

    amount = Column(Float, default=10.0)
    tp_percent = Column(Float, default=2.0)
    sl_percent = Column(Float, default=1.0)

    # === ADD THESE LINES TO STORE TP/SL ARRAYS ===
    tp_levels_json = Column(Text, default='[]')  # Store TP levels
    sl_levels_json = Column(Text, default='[]')  # Store SL levels

    exchange_api_key = relationship("ExchangeAPIKey", backref="bot_configs")
    symbol = relationship("Symbol", backref="bot_configs")
    
class TradeRecord(Base):
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, index=True)
    exchange_api_key_id = Column(Integer, ForeignKey("exchange_api_keys.id"), nullable=False)

    # CHANGED: symbol is now a string, not an integer foreign key
    symbol = Column(String, nullable=False)

    order_id = Column(String, index=True, nullable=True)
    trade_id = Column(String, index=True, nullable=True)
    side = Column(String, nullable=False)      # "buy" or "sell"
    order_type = Column(String, nullable=False)  # e.g. "market", "limit"
    amount = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    fee_currency = Column(String, nullable=True)
    cost = Column(Float, nullable=False)  # Typically amount * price
    pnl = Column(Float, default=0.0)      # Optional

    created_at = Column(DateTime, default=datetime.utcnow)

    exchange_api_key = relationship("ExchangeAPIKey")
    # REMOVED: symbol = relationship("Symbol") (no longer needed)

class OrderLevel(Base):
    __tablename__ = "order_levels"

    id = Column(Integer, primary_key=True, index=True)
    exchange_api_key_id = Column(Integer, ForeignKey("exchange_api_keys.id"), nullable=False)
    symbol = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    order_type = Column(String, nullable=False)  # "tp" or "sl"
    order_id = Column(String, nullable=True)  # Exchange's order ID
    status = Column(String, default="open")  # "open", "filled", "cancelled"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    exchange_api_key = relationship("ExchangeAPIKey")