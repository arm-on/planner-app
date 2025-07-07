from sqlalchemy import Column, Integer, String, DateTime
from core.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy import ForeignKey


class Key(Base):
    __tablename__ = "keys"
    
    key = Column(String, primary_key=True, index=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner_user = relationship("User", foreign_keys=[owner], back_populates="keys")
    expires_at = Column(DateTime, nullable=False)