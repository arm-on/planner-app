from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text, String
from core.database import Base
from sqlalchemy.orm import relationship
from datetime import datetime

class Note(Base):
    __tablename__ = 'notes'
    id = Column(Integer, primary_key=True, index=True)
    when = Column(DateTime, nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    content = Column(Text, nullable=False)

    task = relationship('Task', back_populates='notes')
    attachments = relationship('NoteAttachment', back_populates='note', cascade='all, delete')

class NoteAttachment(Base):
    __tablename__ = 'note_attachments'
    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(Integer, ForeignKey('notes.id'), nullable=False)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    note = relationship('Note', back_populates='attachments') 