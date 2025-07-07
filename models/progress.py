from sqlalchemy import Column, Integer, String, ForeignKey
from core.database import Base
from sqlalchemy.orm import relationship


class Progress(Base):
    __tablename__ = "progress"
    
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False)
    unit = Column(String, nullable=False)
    value = Column(Integer, nullable=False)
    max_value = Column(Integer, nullable=False)
    
    # Relationships
    owner_user = relationship("User", foreign_keys=[owner], back_populates="progress_items")
    tasks = relationship("Task", back_populates="progress")