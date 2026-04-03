from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from core.database import Base


class AssistantMemory(Base):
    __tablename__ = "assistant_memory"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    mode = Column(String, nullable=False, default="assistant", index=True)
    summary = Column(Text, nullable=False, default="")
    recent_history = Column(Text, nullable=False, default="[]")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    owner_user = relationship("User")

