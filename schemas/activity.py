from pydantic import BaseModel, field_validator
from typing import Optional, Union
from datetime import datetime
from enum import Enum
from core.timezone import convert_to_app_timezone

class ActivityStatus(str, Enum):
    PLANNED = "PLANNED"
    DOING = "DOING"
    DONE = "DONE"

# Mapping from API enum values to database enum values
ACTIVITY_STATUS_MAP = {
    "PLANNED": "PLANNED",
    "DOING": "DOING",
    "DONE": "DONE"
}

class ActivityBase(BaseModel):
    clock_in: datetime
    clock_out: Optional[datetime] = None
    task_id: int
    status: ActivityStatus
    description: Optional[str] = None

class ActivityCreate(ActivityBase):
    # Recurring activity fields
    is_recurring: Optional[bool] = False
    days_interval: Optional[int] = None  # Days between recurrences
    recurrence_count: Optional[int] = None  # Number of additional activities to create

class ActivityUpdate(BaseModel):
    clock_in: Optional[datetime] = None
    clock_out: Optional[datetime] = None
    task_id: Optional[int] = None
    status: Optional[ActivityStatus] = None
    description: Optional[str] = None

class ActivityResponse(BaseModel):
    id: int
    clock_in: datetime
    clock_out: Optional[datetime] = None
    task_id: int
    status: ActivityStatus
    description: Optional[str] = None
    
    class Config:
        from_attributes = True
    
    @field_validator('status', mode='before')
    @classmethod
    def convert_status(cls, v):
        if isinstance(v, str):
            # Convert from database string to API enum
            status_map_reverse = {val: key for key, val in ACTIVITY_STATUS_MAP.items()}
            return ActivityStatus(status_map_reverse[v])
        return v
    
    @field_validator('clock_in', mode='before')
    @classmethod
    def convert_clock_in_to_app_timezone(cls, v):
        if isinstance(v, datetime):
            return convert_to_app_timezone(v)
        return v
    
    @field_validator('clock_out', mode='before')
    @classmethod
    def convert_clock_out_to_app_timezone(cls, v):
        if isinstance(v, datetime):
            return convert_to_app_timezone(v)
        return v

class ActivityDetailsResponse(ActivityResponse):
    task_name: str
    project_id: int
    project_name: str
