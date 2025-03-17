from pydantic import BaseModel
from typing import Optional, List

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