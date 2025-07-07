from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from core.database import Base
from core.timezone import DEFAULT_TIMEZONE

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    timezone = Column(String, nullable=False, default=DEFAULT_TIMEZONE)
    
    # Relationships
    models = relationship("Model", back_populates="user")
    keys = relationship("Key", back_populates="owner_user")
    progress_items = relationship("Progress", back_populates="owner_user")
    projects = relationship("Project", back_populates="owner_user")
    tasks = relationship("Task", back_populates="owner_user")
    reminders = relationship("Reminder", back_populates="owner_user")