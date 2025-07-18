from sqlalchemy.orm import Session
from fastapi import Request
from models import keys
from datetime import datetime as dt

def check_user_auth(request: Request, db: Session) -> dict:
    """Check if user is authenticated and return user info"""
    try:
        # Check for API key in cookies (set by frontend)
        api_key = request.cookies.get("apiKey")
        if not api_key:
            return {"is_authenticated": False, "user": None}
        # Check if key exists and is not expired
        key_record = db.query(keys.Key).filter(
            keys.Key.key == api_key,
            keys.Key.expires_at > dt.utcnow()
        ).first()
        if not key_record:
            return {"is_authenticated": False, "user": None}
        return {
            "is_authenticated": True,
            "user": {
                "id": key_record.owner_user.id,
                "username": key_record.owner_user.username,
                "display_name": key_record.owner_user.display_name
            }
        }
    except Exception:
        return {"is_authenticated": False, "user": None} 