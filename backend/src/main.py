from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import models, schemas, crud
from database.database import SessionLocal, engine
from grid_logic.grid_strategy import grid_bot
from grid_logic.schema import StartSymbolParams, StopSymbolRequest
from fastapi.middleware.cors import CORSMiddleware
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import uvicorn
import requests
import logging 
import ccxt
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Create tables if they don't exist
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Trading Bot API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Dependency to get a DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------# ---------------- # Api key endpoints # ----------------# ----------------# 
# ----------------# ----------------# ----------------# ----------------# ----------------# ----------------
@app.post("/api-keys/", response_model=schemas.APIKey)
def add_api_key(api_key: schemas.APIKeyCreate, db: Session = Depends(get_db)):
    # Ensure only one key pair per exchange
    existing = db.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange == api_key.exchange.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="API key for this exchange already exists.")

    # Convert PEM-encoded api_secret for Coinbase
    if api_key.exchange.lower() == "coinbase":
        try:
            pem_key = api_key.api_secret
            private_key = serialization.load_pem_private_key(
                pem_key.encode(), password=None, backend=default_backend()
            )
            raw_private_key = private_key.private_numbers().private_value.to_bytes(32, byteorder='big')
            api_key.api_secret = raw_private_key.hex()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to convert PEM-encoded key for Coinbase: {str(e)}"
            )

    return crud.create_api_key(db, api_key)

@app.get("/api-keys/{exchange}", response_model=schemas.APIKey)
def get_api_key(exchange: str, db: Session = Depends(get_db)):
    exchange = exchange.lower()  # Convert input to lowercase
    key = db.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange == exchange).first()
    if not key:
        raise HTTPException(status_code=404, detail="No API key found for this exchange.")
    return key

@app.put("/api-keys/{exchange}", response_model=schemas.APIKey)
def update_api_key(exchange: str, updated_key: schemas.APIKeyCreate, db: Session = Depends(get_db)):
    key = db.query(models.ExchangeAPIKey).filter(models.ExchangeAPIKey.exchange == exchange.lower()).first()
    if not key:
        raise HTTPException(status_code=404, detail="No API key found for this exchange.")

    # Convert PEM-encoded api_secret for Coinbase if needed
    if exchange.lower() == "coinbase" and updated_key.api_secret:
        try:
            pem_key = updated_key.api_secret
            private_key = serialization.load_pem_private_key(
                pem_key.encode(), password=None, backend=default_backend()
            )
            raw_private_key = private_key.private_numbers().private_value.to_bytes(32, byteorder='big')
            updated_key.api_secret = raw_private_key.hex()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to convert PEM-encoded key for Coinbase: {str(e)}"
            )

    # ✅ Update only provided fields
    key.api_key = updated_key.api_key if updated_key.api_key else key.api_key
    key.api_secret = updated_key.api_secret if updated_key.api_secret else key.api_secret
    key.balance = updated_key.balance if updated_key.balance else key.balance
    key.leverage = updated_key.leverage if updated_key.leverage else key.leverage

    db.commit()
    db.refresh(key)
    return key


@app.delete("/api-keys/{exchange}")
def delete_api_key(exchange: str, db: Session = Depends(get_db)):
    deleted_key = crud.delete_api_key(db, exchange)
    
    if not deleted_key:
        raise HTTPException(status_code=404, detail="No API key found for this exchange.")
    
    return {"message": f"API key for {exchange} deleted successfully."}


# ---------------- # ----------------# Grid Endpoints # ----------------# ----------------# ----------------
# ----------------# ----------------# ----------------# ----------------# ----------------# ----------------

@app.post("/grid-bot/start-symbol")
def start_symbol_endpoint(params: StartSymbolParams, db: Session = Depends(get_db)):
    """
    Starts a single symbol on a given exchange.
    Ensures that at least one exchange is selected.
    """
    if not params.exchange:
        raise HTTPException(status_code=400, detail="Error: No exchange selected. Please select at least one exchange.")

    grid_bot.start_symbol(params.exchange, params.symbol, db)
    return {
        "message": f"Started symbol {params.symbol} on exchange {params.exchange}"
    }
    
@app.post("/stop_symbol")
async def stop_symbol(request: StopSymbolRequest):
    """Stop WebSocket for a specific symbol on a specific exchange"""
    try:
        grid_bot.stop_symbol(request.symbol, request.exchange)
        return {"status": "success", "message": f"Stopped WebSocket for {request.symbol} on {request.exchange or 'all exchanges'}"}
    except Exception as e:
        logger.error(f"Error stopping WebSocket: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/grid-bot/status")
def get_grid_bot_status(symbol: Optional[str] = None):
    """
    Returns the grid bot's global status ('running' or 'stopped') and symbol-specific statuses.
    If a symbol is provided, only return that symbol's status.
    Otherwise, return all symbols' statuses.
    """
    global_status = "running" if grid_bot.running else "stopped"
    if symbol:
        symbol_status = grid_bot.get_symbol_status(symbol)
        return {"global_status": global_status, "symbol_status": {symbol: symbol_status}}
    else:
        all_status = grid_bot.get_all_symbols_status()
        return {"global_status": global_status, "active_symbols": all_status}
# ---------------- # ----------------# Symbols Endpoints # ----------------# ----------------# ----------------
# ----------------# ----------------# ----------------# ----------------# ----------------# ----------------

@app.post("/grid-bot/restart")
def restart_grid_bot(exchange_name: str, symbol: str, db: Session = Depends(get_db)):
    """
    Cleans and restarts the bot configuration for a specific symbol using the exchange name.
    """
    try:
        # Fetch the exchange entry by name
        exchange_entry = crud.get_api_key_by_exchange(db, exchange_name)
        if not exchange_entry:
            raise HTTPException(status_code=404, detail=f"Exchange {exchange_name} not found.")

        exchange_id = exchange_entry.id  # Get the correct exchange_id

        # Fetch bot config using exchange name
        bot_config = crud.get_bot_config_by_exchange_symbol(db, exchange_name, symbol)
        if not bot_config:
            raise HTTPException(status_code=404, detail=f"No bot config found for {symbol} on {exchange_name}")

        exchange_instance = grid_bot.connections.get(exchange_name)
        if not exchange_instance:
            raise HTTPException(status_code=400, detail=f"Exchange {exchange_name} is not connected.")

        # Cancel all open orders for this symbol
        open_orders = exchange_instance.fetch_open_orders(symbol)
        for order in open_orders:
            try:
                exchange_instance.cancel_order(order["id"], symbol)
                logger.info(f"Cancelled order {order['id']} for {symbol} on {exchange_name}")
            except Exception as e:
                logger.error(f"Failed to cancel order {order['id']} for {symbol}: {str(e)}")

        # Delete bot config
        db.delete(bot_config)
        db.commit()
        
        return {"message": f"Bot for {symbol} on {exchange_name} has been restarted."}

    except Exception as e:
        logger.exception(f"Error restarting bot for {symbol} on {exchange_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to restart bot: {str(e)}")

@app.post("/symbols/")
def update_symbols(request: schemas.UpdateSymbolsRequest, db: Session = Depends(get_db)):
    """
    Updates TP/SL values for stored symbols. Does NOT store `amount`, as it comes from API Key balance.
    """
    current_symbols = {s.symbol: s for s in crud.get_all_symbols(db)}
    new_symbols_set = {s.symbol for s in request.symbols}

    added_symbols = []
    updated_symbols = []
    removed_symbols = []

    exchanges = db.query(models.ExchangeAPIKey).all()  # Fetch all exchange keys

    for sym_update in request.symbols:
        if sym_update.symbol not in current_symbols:
            # ✅ Create new symbol
            new_sym = crud.add_symbol(db, sym_update.symbol)
            if new_sym:
                added_symbols.append(new_sym.symbol)

                # ✅ Create bot configurations for all exchanges with correct amount
                for ex in exchanges:
                    config_data = schemas.ExchangeBotConfigCreate(
                        exchange_id=ex.id,
                        symbol_id=new_sym.id,
                        amount=ex.balance,  # ✅ Fetch the amount from exchange balance
                        tp_percent=sym_update.tp_percent,
                        sl_percent=sym_update.sl_percent,
                        tp_levels_json='[]',
                        sl_levels_json='[]'
                    )
                    crud.create_bot_config(db, config_data)
        else:
            # ✅ Update existing symbol's TP/SL values
            symbol_obj = current_symbols[sym_update.symbol]
            bot_configs = db.query(models.ExchangeBotConfig).filter(
                models.ExchangeBotConfig.symbol_id == symbol_obj.id
            ).all()

            if bot_configs:
                for config in bot_configs:
                    config.tp_percent = sym_update.tp_percent
                    config.sl_percent = sym_update.sl_percent
                updated_symbols.append(sym_update.symbol)
            else:
                # ✅ Ensure a bot config exists for each exchange
                for ex in exchanges:
                    config_data = schemas.ExchangeBotConfigCreate(
                        exchange_id=ex.id,
                        symbol_id=symbol_obj.id,
                        amount=ex.balance,  # ✅ Fetch the amount from exchange balance
                        tp_percent=sym_update.tp_percent,
                        sl_percent=sym_update.sl_percent,
                        tp_levels_json='[]',
                        sl_levels_json='[]'
                    )
                    crud.create_bot_config(db, config_data)
                updated_symbols.append(sym_update.symbol)

    db.commit()

    # ✅ Remove symbols not in the request
    current_symbols_set = set(current_symbols.keys())
    symbols_to_remove = current_symbols_set - new_symbols_set

    for sym in symbols_to_remove:
        removed = crud.remove_symbol(db, sym)
        if removed:
            removed_symbols.append(removed.symbol)
            bot_configs = db.query(models.ExchangeBotConfig).filter(
                models.ExchangeBotConfig.symbol_id == removed.id
            ).all()
            for config in bot_configs:
                crud.delete_bot_config(db, config.id)

    return {
        "message": "Symbols updated successfully.",
        "added": added_symbols,
        "updated": updated_symbols,
        "removed": removed_symbols,
        "current": list(new_symbols_set)
    }
  
@app.get("/symbols/")
def get_symbols(db: Session = Depends(get_db)):
    """
    Retrieve all stored symbols along with their bot configuration (TP/SL) for each exchange.
    """
    symbols = crud.get_all_symbols(db)
    result = []
    for s in symbols:
        # Retrieve bot configurations for each symbol
        configs = db.query(models.ExchangeBotConfig)\
            .join(models.Symbol)\
            .filter(models.Symbol.id == s.id).all()
        config_list = []
        for cfg in configs:
            config_list.append({
                "exchange": cfg.exchange_api_key.exchange,
                "amount": cfg.amount,
                "tp_percent": cfg.tp_percent,
                "sl_percent": cfg.sl_percent,
                "tp_levels": cfg.tp_levels_json,
                "sl_levels": cfg.sl_levels_json
            })
        result.append({
            "symbol": s.symbol,
            "configs": config_list
        })
    return {"symbols": result}


# ---------------- # Symbols List Fetching # ----------------

@app.get("/list/symbols/")
def get_usdc_usdt_symbols():
    """
    Fetches all tradable USDC and USDT pairs from Binance exchangeInfo API.
    """
    binance_url = "https://api.binance.com/api/v3/exchangeInfo"

    try:
        response = requests.get(binance_url)
        response.raise_for_status()
        data = response.json()

        if "symbols" not in data:
            raise HTTPException(status_code=500, detail="Invalid response from Binance API")

        # Extracting USDC and USDT pairs and formatting as BASE/QUOTE
        symbols = [
            f"{s['baseAsset']}/{s['quoteAsset']}"
            for s in data["symbols"]
            if s["quoteAsset"] in ["USDC", "USDT"] and s["status"] == "TRADING"
        ]

        return {"symbols": symbols}

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error fetching Binance symbols: {str(e)}")

# ---------------- # Portfolio Endpoints # ----------------


@app.get("/portfolio", response_model=schemas.PortfolioResponse)
def get_portfolio(db: Session = Depends(get_db)):
    # Query only symbols that have at least one trade record.
    symbols = db.query(models.Symbol).join(
                models.TradeRecord, 
                models.Symbol.symbol == models.TradeRecord.symbol
            ).distinct().all()
    portfolio_list = []

    for symbol in symbols:
        trades = crud.get_trade_records_by_symbol(db, symbol.id)
        total_invested = sum(trade.cost for trade in trades if trade.side.lower() == "buy")
        total_received = sum(trade.cost for trade in trades if trade.side.lower() == "sell")
        pnl = total_received - total_invested

        portfolio_list.append({
            "symbol": symbol.symbol,
            "totalCost": total_invested,
            "totalPnl": pnl,
            "trades": trades
        })

    return {"portfolio": portfolio_list}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)