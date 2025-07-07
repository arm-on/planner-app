from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from core.database import Base
from sqlalchemy.orm import relationship
from enum import Enum


class EnergyLevel(Enum):
    HIGH = 3
    MEDIUM = 2
    LOW = 1
    
class TaskState(Enum):
    OPEN = "open"
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    CLOSED = "closed"

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    proj_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    is_important = Column(Boolean, nullable=False)
    is_urgent = Column(Boolean, nullable=False)
    energy_level = Column(Integer, nullable=False)  # Store as integer
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    state = Column(String, nullable=False)  # Store as string
    deadline = Column(DateTime, nullable=True)
    progress_id = Column(Integer, ForeignKey("progress.id"), nullable=False)
    
    # Relationships
    owner_user = relationship("User", foreign_keys=[owner], back_populates="tasks")
    proj = relationship("Project", foreign_keys=[proj_id], back_populates="tasks")
    parent_task = relationship("Task", foreign_keys=[parent_task_id], remote_side=[id])
    progress = relationship("Progress", foreign_keys=[progress_id], back_populates="tasks")
    activities = relationship("Activity", back_populates="task")
    