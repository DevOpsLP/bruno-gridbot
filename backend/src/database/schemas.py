from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class APIKeyBase(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    balance: float
    leverage: float

class APIKeyCreate(APIKeyBase):
    pass

class APIKey(APIKeyBase):
    id: int

    class Config:
        orm_mode = True
        
class ExchangeBotConfigBase(BaseModel):
    exchange_id: int
    symbol_id: int
    amount: float
    tp_percent: float
    sl_percent: float
    tp_levels_json: Optional[str] = '[]'  # added default empty JSON array
    sl_levels_json: Optional[str] = '[]'
    

class ExchangeBotConfigCreate(ExchangeBotConfigBase):
    pass

class ExchangeBotConfig(ExchangeBotConfigBase):
    id: int

    class Config:
        orm_mode = True


class SymbolUpdate(BaseModel):
    symbol: str
    tp_percent: float
    sl_percent: float

class UpdateSymbolsRequest(BaseModel):
    symbols: List[SymbolUpdate]

class TradeRecordBase(BaseModel):
    exchange_api_key_id: int
    symbol_id: int
    order_id: Optional[str] = None
    trade_id: Optional[str] = None
    side: str
    order_type: str
    amount: float
    price: float
    fee: Optional[float] = 0.0
    fee_currency: Optional[str] = None
    cost: float
    pnl: Optional[float] = 0.0

class TradeRecord(TradeRecordBase):
    id: int
    created_at: datetime

    class Config:
        orm_mode = True

class PortfolioSymbol(BaseModel):
    symbol: str
    totalInvested: float
    totalPnl: float
    trades: List[TradeRecord]

class PortfolioResponse(BaseModel):
    portfolio: List[PortfolioSymbol]