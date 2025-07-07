from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from models.progress import Progress
from models.user import User
from models.keys import Key
from schemas.progress import ProgressCreate, ProgressUpdate, ProgressResponse

router = APIRouter(prefix="/progress", tags=["progress"])

def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from API key in header"""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    # Check if key exists and is not expired
    key_record = db.query(Key).filter(
        Key.key == x_api_key,
        Key.expires_at > datetime.utcnow()
    ).first()
    
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    return key_record.owner_user

@router.post("/", response_model=ProgressResponse)
def create_progress(
    progress: ProgressCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new progress item"""
    # Validate that value doesn't exceed max_value
    if progress.value > progress.max_value:
        raise HTTPException(status_code=400, detail="Value cannot exceed max_value")
    
    db_progress = Progress(
        owner=current_user.id,
        unit=progress.unit,
        value=progress.value,
        max_value=progress.max_value
    )
    db.add(db_progress)
    db.commit()
    db.refresh(db_progress)
    return db_progress

@router.get("/", response_model=List[ProgressResponse])
def get_progress_items(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all progress items for the authenticated user"""
    progress_items = db.query(Progress).filter(
        Progress.owner == current_user.id
    ).offset(skip).limit(limit).all()
    return progress_items

@router.get("/{progress_id}", response_model=ProgressResponse)
def get_progress_item(
    progress_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific progress item (only if owned by authenticated user)"""
    progress_item = db.query(Progress).filter(
        Progress.id == progress_id,
        Progress.owner == current_user.id
    ).first()
    if progress_item is None:
        raise HTTPException(status_code=404, detail="Progress item not found")
    return progress_item

@router.put("/{progress_id}", response_model=ProgressResponse)
def update_progress_item(
    progress_id: int, 
    progress_update: ProgressUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a progress item (only if owned by authenticated user)
    
    Supports partial updates - only send the fields you want to change.
    Examples:
    - Update only value: {"value": 75}
    - Update only unit: {"unit": "chapters"}
    - Update multiple fields: {"value": 75, "max_value": 100}
    """
    db_progress = db.query(Progress).filter(
        Progress.id == progress_id,
        Progress.owner == current_user.id
    ).first()
    if db_progress is None:
        raise HTTPException(status_code=404, detail="Progress item not found")
    
    # Update fields if provided
    update_data = progress_update.dict(exclude_unset=True)
    
    # Validate that value doesn't exceed max_value if both are being updated
    if 'value' in update_data and 'max_value' in update_data:
        if update_data['value'] > update_data['max_value']:
            raise HTTPException(status_code=400, detail="Value cannot exceed max_value")
    elif 'value' in update_data and 'max_value' not in update_data:
        if update_data['value'] > db_progress.max_value:
            raise HTTPException(status_code=400, detail="Value cannot exceed max_value")
    elif 'max_value' in update_data and 'value' not in update_data:
        if db_progress.value > update_data['max_value']:
            raise HTTPException(status_code=400, detail="Value cannot exceed max_value")
    
    for field, value in update_data.items():
        setattr(db_progress, field, value)
    
    db.commit()
    db.refresh(db_progress)
    return db_progress

@router.patch("/{progress_id}", response_model=ProgressResponse)
def patch_progress_item(
    progress_id: int, 
    progress_update: ProgressUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch a progress item (partial update, only if owned by authenticated user)
    
    This is an alternative to PUT for partial updates. Both PUT and PATCH work the same way.
    Only send the fields you want to change.
    """
    return update_progress_item(progress_id, progress_update, current_user, db)

@router.delete("/{progress_id}")
def delete_progress_item(
    progress_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a progress item (only if owned by authenticated user)"""
    db_progress = db.query(Progress).filter(
        Progress.id == progress_id,
        Progress.owner == current_user.id
    ).first()
    if db_progress is None:
        raise HTTPException(status_code=404, detail="Progress item not found")
    
    db.delete(db_progress)
    db.commit()
    return {"message": "Progress item deleted successfully"}