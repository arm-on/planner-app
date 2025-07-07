from sqlalchemy import Column, Integer, String, ForeignKey
from core.database import Base
from sqlalchemy.orm import relationship


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)
    
    # Relationships
    owner_user = relationship("User", foreign_keys=[owner], back_populates="projects")
    tasks = relationship("Task", back_populates="proj")