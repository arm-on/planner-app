from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel, EmailStr
from core.database import get_db
from core.user import get_current_user
from models.user import User
from models.keys import Key
from datetime import datetime, timedelta
import secrets
import string
from core.timezone import DEFAULT_TIMEZONE, get_timezones_by_country

router = APIRouter(prefix="/users", tags=["users"])

# Pydantic schemas
class UserCreate(BaseModel):
    username: str
    display_name: str
    password: str
    email: EmailStr

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    email: str
    timezone: str

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    api_key: str
    user_id: int
    username: str
    display_name: str

class TimezoneUpdate(BaseModel):
    timezone: str

class TimezoneResponse(BaseModel):
    timezone: str
    available_timezones: dict = {}

def generate_api_key(length: int = 32) -> str:
    """Generate a random API key"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

from core.user import get_current_user

@router.post("/", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    db_user = User(
        username=user_data.username,
        display_name=user_data.display_name,
        password=user_data.password,  # In production, hash this password
        email=user_data.email,
        timezone=DEFAULT_TIMEZONE
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Generate API key with expiration (30 days from now)
    api_key = generate_api_key()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    # Create key record
    db_key = Key(
        key=api_key,
        owner=db_user.id,
        expires_at=expires_at
    )
    
    db.add(db_key)
    db.commit()
    
    return db_user

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user (same as create_user but with different endpoint)
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    db_user = User(
        username=user_data.username,
        display_name=user_data.display_name,
        password=user_data.password,  # In production, hash this password
        email=user_data.email,
        timezone=DEFAULT_TIMEZONE
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

@router.put("/me", response_model=UserResponse)
async def edit_current_user(
    user_data: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edit the current authenticated user
    
    Supports partial updates - only send the fields you want to change.
    Examples:
    - Update only display name: {"display_name": "New Name"}
    - Update only email: {"email": "newemail@example.com"}
    - Update only password: {"password": "newpassword"}
    - Update multiple fields: {"display_name": "New Name", "email": "newemail@example.com"}
    - Update all fields: {"display_name": "New Name", "email": "newemail@example.com", "password": "newpassword"}
    """
    # Update fields if provided
    if user_data.display_name is not None:
        current_user.display_name = user_data.display_name
    
    if user_data.password is not None:
        current_user.password = user_data.password  # In production, hash this password
    
    if user_data.email is not None:
        # Check if email is already taken by another user
        existing_email = db.query(User).filter(
            User.email == user_data.email, 
            User.id != current_user.id
        ).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email already taken")
        current_user.email = user_data.email
    
    if user_data.timezone is not None:
        current_user.timezone = user_data.timezone
    
    db.commit()
    db.refresh(current_user)
    
    return current_user

@router.patch("/me", response_model=UserResponse)
async def patch_current_user(
    user_data: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch the current authenticated user (partial update)
    
    This is an alternative to PUT for partial updates. Both PUT and PATCH work the same way.
    Only send the fields you want to change.
    """
    return await edit_current_user(user_data, current_user, db)

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user info
    """
    return current_user

@router.post("/login", response_model=LoginResponse)
async def login_user(login_data: UserLogin, db: Session = Depends(get_db)):
    """
    Login user with username and password, returns API key
    """
    # Find user by username
    user = db.query(User).filter(User.username == login_data.username).first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Check password (in production, use proper password hashing)
    if user.password != login_data.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    # Generate new API key with expiration (30 days from now)
    api_key = generate_api_key()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    # Create new key record
    db_key = Key(
        key=api_key,
        owner=user.id,
        expires_at=expires_at
    )
    
    db.add(db_key)
    db.commit()
    
    # Return API key and user info
    return LoginResponse(
        api_key=api_key,
        user_id=user.id,
        username=user.username,
        display_name=user.display_name
    )

@router.post("/keys", response_model=LoginResponse)
async def create_api_key(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new API key for the authenticated user
    """
    # Generate new API key with expiration (30 days from now)
    api_key = generate_api_key()
    expires_at = datetime.utcnow() + timedelta(days=30)
    
    # Create new key record
    db_key = Key(
        key=api_key,
        owner=current_user.id,
        expires_at=expires_at
    )
    
    db.add(db_key)
    db.commit()
    
    # Return API key and user info
    return LoginResponse(
        api_key=api_key,
        user_id=current_user.id,
        username=current_user.username,
        display_name=current_user.display_name
    )

@router.get("/keys", response_model=list[dict])
async def get_user_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all API keys for the authenticated user
    """
    keys = db.query(Key).filter(Key.owner == current_user.id).all()
    return [
        {
            "key": key.key,
            "expires_at": key.expires_at,
            "is_expired": key.expires_at <= datetime.utcnow()
        }
        for key in keys
    ]

@router.post("/timezone", response_model=TimezoneResponse)
async def update_timezone(
    timezone_data: TimezoneUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the timezone for the authenticated user
    """
    current_user.timezone = timezone_data.timezone
    db.commit()
    db.refresh(current_user)
    
    return TimezoneResponse(timezone=current_user.timezone)

@router.get("/timezone", response_model=TimezoneResponse)
async def get_timezone(current_user: User = Depends(get_current_user)):
    """
    Get the timezone for the authenticated user
    """
    return TimezoneResponse(
        timezone=current_user.timezone,
        available_timezones=get_timezones_by_country()
    )
