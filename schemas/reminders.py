from pydantic import BaseModel, field_serializer
from datetime import datetime
from typing import Optional

class ReminderBase(BaseModel):
    when: datetime
    note: str

class ReminderCreate(ReminderBase):
    pass

class ReminderUpdate(BaseModel):
    when: Optional[datetime] = None
    note: Optional[str] = None

class ReminderResponse(ReminderBase):
    id: int
    owner_id: int
    
    @field_serializer('when')
    def serialize_when(self, when: datetime) -> str:
        """Convert naive datetime to UTC ISO string for frontend"""
        if when.tzinfo is None:
            # Assume naive datetime is UTC and convert to UTC ISO string
            return when.isoformat() + 'Z'
        else:
            # Convert to UTC ISO string
            return when.astimezone().isoformat()
    
    class Config:
        from_attributes = True
