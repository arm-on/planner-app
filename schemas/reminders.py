from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Optional

class ReminderBase(BaseModel):
    when: Optional[datetime] = None
    note: str
    is_timeless: bool = True

class ReminderCreate(ReminderBase):
    pass

class ReminderUpdate(BaseModel):
    when: Optional[datetime] = None
    note: Optional[str] = None

class ReminderResponse(ReminderBase):
    id: int
    owner_id: int
    
    @field_serializer('when')
    def serialize_when(self, when: Optional[datetime]) -> Optional[str]:
        if when is None:
            return None
        if when.tzinfo is None:
            return when.isoformat() + 'Z'
        return when.astimezone().isoformat()
    
    class Config:
        from_attributes = True
