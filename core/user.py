from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from datetime import datetime
from core.database import get_db
from models.user import User
from models.keys import Key

def get_current_user(api_key: str = Header(..., alias="X-API-Key"), db: Session = Depends(get_db)) -> User:
    """Get current user from API key"""
    # Check if key exists and is not expired
    key_record = db.query(Key).filter(
        Key.key == api_key,
        Key.expires_at > datetime.utcnow()
    ).first()
    
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    return key_record.owner_user 