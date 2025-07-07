from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base

class Model(Base):
    __tablename__ = "models"
    api_key = Column(String, nullable=False, unique=True, primary_key=True)
    owner = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    base_url = Column(String, nullable=False)
    user = relationship("User", foreign_keys=[owner], back_populates="models")
    