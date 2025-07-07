from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from core.database import Base
from sqlalchemy.orm import relationship
from enum import Enum


class ActivityStatus(Enum):
    PLANNED = "PLANNED"
    DOING = "DOING"
    DONE = "DONE"


class Activity(Base):
    __tablename__ = "activities"
    
    id = Column(Integer, primary_key=True, index=True)
    clock_in = Column(DateTime, nullable=False)
    clock_out = Column(DateTime, nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    status = Column(String, nullable=False)  # Store as string
    description = Column(String, nullable=True)  # Optional description field
    
    # Relationships
    task = relationship("Task", foreign_keys=[task_id], back_populates="activities")
