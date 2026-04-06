from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date, timedelta
import pytz

from core.database import get_db
from core.user import get_current_user
from core.timezone import convert_from_timezone, convert_to_timezone
from models.reminders import Reminder
from models.user import User
from schemas.reminders import ReminderCreate, ReminderUpdate, ReminderResponse

router = APIRouter(prefix="/reminders", tags=["reminders"])

@router.post("/", response_model=ReminderResponse)
def create_reminder(
    reminder: ReminderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new reminder for the current user."""
    # Convert the reminder time from user's timezone to UTC for storage
    user_timezone = current_user.timezone
    
    utc_when = None
    if reminder.when is not None:
        utc_when = convert_from_timezone(reminder.when, user_timezone)
    
    db_reminder = Reminder(
        owner_id=current_user.id,
        when=utc_when,
        note=reminder.note,
        is_timeless=1 if reminder.is_timeless or reminder.when is None else 0
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    return db_reminder

@router.get("/", response_model=List[ReminderResponse])
def get_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all reminders for the current user."""
    reminders = db.query(Reminder).filter(Reminder.owner_id == current_user.id).all()
    return reminders

@router.get("/today", response_model=List[ReminderResponse])
def get_today_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get reminders for today for the current user in their timezone."""
    user_timezone = current_user.timezone
    
    # Get current date in user's timezone
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    
    # Convert to UTC for database query
    utc_start = today_start.astimezone(pytz.UTC)
    utc_end = today_end.astimezone(pytz.UTC)
    
    # Convert to naive datetimes for SQLite compatibility (UTC)
    naive_utc_start = utc_start.replace(tzinfo=None)
    naive_utc_end = utc_end.replace(tzinfo=None)
    
    
    reminders = db.query(Reminder).filter(
        Reminder.owner_id == current_user.id,
        ((Reminder.is_timeless == 1) | ((Reminder.when >= naive_utc_start) & (Reminder.when <= naive_utc_end)))
    ).order_by(Reminder.when).all()
    
    return reminders

@router.get("/date-range", response_model=List[ReminderResponse])
def get_reminders_by_date_range(
    start_date: str,  # YYYY-MM-DD
    end_date: str,    # YYYY-MM-DD
    timezone: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get reminders for the current user within a date range (inclusive, in user's timezone)"""
    import pytz
    from datetime import datetime, timedelta
    user_timezone = timezone or current_user.timezone or "UTC"
    tz = pytz.timezone(user_timezone)
    # Parse start and end dates in user's timezone
    try:
        start_dt = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = tz.localize(datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)) - timedelta(microseconds=1)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    # Convert to UTC for DB query
    start_dt_utc = start_dt.astimezone(pytz.UTC)
    end_dt_utc = end_dt.astimezone(pytz.UTC)
    # Convert to naive datetimes for SQLite
    naive_utc_start = start_dt_utc.replace(tzinfo=None)
    naive_utc_end = end_dt_utc.replace(tzinfo=None)
    reminders = db.query(Reminder).filter(
        Reminder.owner_id == current_user.id,
        ((Reminder.is_timeless == 1) | ((Reminder.when >= naive_utc_start) & (Reminder.when <= naive_utc_end)))
    ).order_by(Reminder.when).all()
    return reminders

@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific reminder by ID."""
    reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.owner_id == current_user.id
    ).first()
    
    if not reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    return reminder

@router.put("/{reminder_id}", response_model=ReminderResponse)
def update_reminder(
    reminder_id: int,
    reminder_update: ReminderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a reminder (partial update supported)."""
    db_reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.owner_id == current_user.id
    ).first()
    
    if not db_reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    # Update only provided fields
    if reminder_update.when is not None:
        user_timezone = current_user.timezone
        utc_when = convert_from_timezone(reminder_update.when, user_timezone)
        db_reminder.when = utc_when
        db_reminder.is_timeless = 0
    elif reminder_update.when is None and reminder_update.note is not None and getattr(reminder_update, "is_timeless", None) is True:
        db_reminder.when = None
        db_reminder.is_timeless = 1
    if reminder_update.note is not None:
        db_reminder.note = reminder_update.note
    if reminder_update.is_timeless is not None:
        db_reminder.is_timeless = 1 if reminder_update.is_timeless else 0
        if reminder_update.is_timeless:
            db_reminder.when = None
    
    db.commit()
    db.refresh(db_reminder)
    return db_reminder

@router.delete("/{reminder_id}")
def delete_reminder(
    reminder_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a reminder."""
    db_reminder = db.query(Reminder).filter(
        Reminder.id == reminder_id,
        Reminder.owner_id == current_user.id
    ).first()
    
    if not db_reminder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reminder not found"
        )
    
    db.delete(db_reminder)
    db.commit()
    return {"message": "Reminder deleted successfully"}
