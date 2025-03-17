from sqlalchemy.orm import Session
from . import models, schemas
import json

# === API Key Management ===

def create_api_key(db: Session, api_key: schemas.APIKeyCreate):
    db_api_key = models.ExchangeAPIKey(
        exchange=api_key.exchange.lower(),
        api_key=api_key.api_key,
        api_secret=api_key.api_secret,
        balance=api_key.balance,
        leverage=api_key.leverage
    )
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    return db_api_key

def delete_api_key(db: Session, exchange: str):
    key = db.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange.ilike(exchange)).first()
    if key:
        db.delete(key)
        db.commit()
    return key

def get_api_key_by_exchange(db: Session, exchange: str):
    return db.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange.ilike(exchange)).first()

# === SYMBOL MANAGEMENT (kept as is) ===

def add_symbol(db: Session, symbol: str):
    symbol = symbol.upper()
    existing_symbol = db.query(models.Symbol).filter(models.Symbol.symbol == symbol).first()
    if existing_symbol:
        return None
    new_symbol = models.Symbol(symbol=symbol)
    db.add(new_symbol)
    db.commit()
    db.refresh(new_symbol)
    return new_symbol

def remove_symbol(db: Session, symbol: str):
    symbol_entry = db.query(models.Symbol).filter(models.Symbol.symbol.ilike(symbol)).first()
    if symbol_entry:
        db.delete(symbol_entry)
        db.commit()
    return symbol_entry

def get_all_symbols(db: Session):
    return db.query(models.Symbol).all()

# === BOT CONFIG MANAGEMENT ===

def create_bot_config(db: Session, config_data: schemas.ExchangeBotConfigCreate):
    db_config = models.ExchangeBotConfig(
        exchange_id=config_data.exchange_id,
        symbol_id=config_data.symbol_id,
        amount=config_data.amount,
        tp_percent=config_data.tp_percent,
        sl_percent=config_data.sl_percent,
        tp_levels_json=config_data.tp_levels_json or '[]',
        sl_levels_json=config_data.sl_levels_json or '[]'
    )
    db.add(db_config)
    db.commit()
    db.refresh(db_config)
    return db_config

def get_bot_config_by_id(db: Session, config_id: int):
    return db.query(models.ExchangeBotConfig).filter(models.ExchangeBotConfig.id == config_id).first()

def get_bot_config_by_exchange_symbol(db: Session, exchange: str, symbol: str):
    return db.query(models.ExchangeBotConfig)\
        .join(models.ExchangeAPIKey)\
        .join(models.Symbol)\
        .filter(
            models.ExchangeAPIKey.exchange.ilike(exchange),
            models.Symbol.symbol.ilike(symbol)
        ).first()

def get_all_bot_configs(db: Session):
    return db.query(models.ExchangeBotConfig).all()

def update_bot_config(db: Session, config_id: int, updated_data: schemas.ExchangeBotConfigCreate):
    db_config = get_bot_config_by_id(db, config_id)
    if not db_config:
        return None

    db_config.exchange_id = updated_data.exchange_id
    db_config.symbol_id = updated_data.symbol_id
    db_config.amount = updated_data.amount
    db_config.tp_percent = updated_data.tp_percent
    db_config.sl_percent = updated_data.sl_percent
    # Update TP/SL arrays if provided; otherwise, keep existing ones.
    db_config.tp_levels_json = updated_data.tp_levels_json or db_config.tp_levels_json
    db_config.sl_levels_json = updated_data.sl_levels_json or db_config.sl_levels_json

    db.commit()
    db.refresh(db_config)
    return db_config

def delete_bot_config(db: Session, config_id: int):
    db_config = get_bot_config_by_id(db, config_id)
    if db_config:
        db.delete(db_config)
        db.commit()
    return db_config

# === Helper methods for TP and SL arrays ===

def get_stored_levels(db: Session, config_id: int):
    bot_config = get_bot_config_by_id(db, config_id)
    if bot_config:
        tp_levels = json.loads(bot_config.tp_levels_json) if bot_config.tp_levels_json else []
        sl_levels = json.loads(bot_config.sl_levels_json) if bot_config.sl_levels_json else []
        return tp_levels, sl_levels
    return [], []

def update_stored_levels(db: Session, config_id: int, tp_levels: list, sl_levels: list):
    bot_config = get_bot_config_by_id(db, config_id)
    if bot_config:
        bot_config.tp_levels_json = json.dumps(tp_levels)
        bot_config.sl_levels_json = json.dumps(sl_levels)
        db.commit()
        db.refresh(bot_config)
    return bot_config