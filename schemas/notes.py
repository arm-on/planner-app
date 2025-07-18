from pydantic import BaseModel
from datetime import datetime
from typing import List

class NoteAttachmentBase(BaseModel):
    filename: str
    filepath: str
    uploaded_at: datetime

class NoteAttachmentResponse(NoteAttachmentBase):
    id: int
    class Config:
        orm_mode = True

class NoteBase(BaseModel):
    when: datetime
    task_id: int
    content: str

class NoteCreate(NoteBase):
    pass

class NoteResponse(NoteBase):
    id: int
    attachments: List[NoteAttachmentResponse] = []
    class Config:
        orm_mode = True 