from pydantic import BaseModel
from typing import List


class StartSymbolParams(BaseModel):
    exchange: str
    symbol: str
    
class StopSymbolRequest(BaseModel):
    symbol: str
    exchange: str