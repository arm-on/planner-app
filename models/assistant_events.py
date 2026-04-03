from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from core.database import Base


class AssistantEvent(Base):
    __tablename__ = "assistant_events"

    id = Column(Integer, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False, default="assistant")
    action_type = Column(String, nullable=True, index=True)
    status = Column(String, nullable=True, index=True)
    payload = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    owner_user = relationship("User")
