from pydantic import BaseModel, EmailStr
from typing import Optional
from core.timezone import DEFAULT_TIMEZONE, get_timezones_by_country

class UserBase(BaseModel):
    username: str
    display_name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None

class UserResponse(UserBase):
    id: int
    timezone: str

    class Config:
        from_attributes = True

class TimezoneUpdate(BaseModel):
    timezone: str

class TimezoneResponse(BaseModel):
    timezone: str
    available_timezones: dict = {} 