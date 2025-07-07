from pydantic import BaseModel
from typing import Optional

class ModelBase(BaseModel):
    name: str
    base_url: str

class ModelCreate(ModelBase):
    api_key: str

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None

class ModelResponse(ModelBase):
    api_key: str
    owner: int
    
    class Config:
        from_attributes = True 