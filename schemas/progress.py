from pydantic import BaseModel
from typing import Optional

class ProgressBase(BaseModel):
    unit: str
    value: int
    max_value: int

class ProgressCreate(ProgressBase):
    pass

class ProgressUpdate(BaseModel):
    unit: Optional[str] = None
    value: Optional[int] = None
    max_value: Optional[int] = None

class ProgressResponse(ProgressBase):
    id: int
    owner: int
    
    class Config:
        from_attributes = True 