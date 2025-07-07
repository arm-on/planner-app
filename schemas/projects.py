from pydantic import BaseModel
from typing import Optional

class ProjectBase(BaseModel):
    name: str
    color: str

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: int
    owner: int
    
    class Config:
        from_attributes = True 