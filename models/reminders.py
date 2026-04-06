from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, text
from sqlalchemy.orm import relationship
from core.database import Base

class Reminder(Base):
    __tablename__ = "reminders"
    
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    when = Column(DateTime, nullable=True)
    is_timeless = Column(Integer, nullable=False, server_default=text("0"))
    note = Column(String, nullable=False)
    
    # Relationships
    owner_user = relationship("User", back_populates="reminders")
