from pydantic import BaseModel, field_validator
from typing import Optional, Union
from datetime import datetime
from enum import Enum
from schemas.progress import ProgressResponse

class EnergyLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    
class TaskState(str, Enum):
    OPEN = "open"
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    CLOSED = "closed"

# Mapping from API enum values to database enum values
ENERGY_LEVEL_MAP = {
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1
}

TASK_STATE_MAP = {
    "open": "open",
    "todo": "todo", 
    "doing": "doing",
    "done": "done",
    "closed": "closed"
}

class TaskBase(BaseModel):
    title: str
    proj_id: int
    is_important: bool
    is_urgent: bool
    energy_level: EnergyLevel
    state: TaskState
    deadline: Optional[datetime] = None
    progress_id: int
    parent_task_id: Optional[int] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    proj_id: Optional[int] = None
    is_important: Optional[bool] = None
    is_urgent: Optional[bool] = None
    energy_level: Optional[EnergyLevel] = None
    state: Optional[TaskState] = None
    deadline: Optional[datetime] = None
    progress_id: Optional[int] = None
    parent_task_id: Optional[int] = None

class TaskResponse(BaseModel):
    id: int
    owner: int
    title: str
    proj_id: int
    is_important: bool
    is_urgent: bool
    energy_level: EnergyLevel
    state: TaskState
    deadline: Optional[datetime] = None
    progress_id: int
    parent_task_id: Optional[int] = None
    progress: Optional[ProgressResponse] = None
    
    class Config:
        from_attributes = True
    
    @field_validator('energy_level', mode='before')
    @classmethod
    def convert_energy_level(cls, v):
        if isinstance(v, int):
            # Convert from database integer to API enum
            energy_level_map_reverse = {val: key for key, val in ENERGY_LEVEL_MAP.items()}
            return EnergyLevel(energy_level_map_reverse[v])
        return v
    
    @field_validator('state', mode='before')
    @classmethod
    def convert_state(cls, v):
        if isinstance(v, str):
            # Convert from database string to API enum
            state_map_reverse = {val: key for key, val in TASK_STATE_MAP.items()}
            return TaskState(state_map_reverse[v])
        return v 