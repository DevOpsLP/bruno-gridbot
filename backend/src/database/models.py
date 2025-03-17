from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
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