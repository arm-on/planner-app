from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, date
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
    print(f"DEBUG: Creating reminder with when={reminder.when}, user_timezone={user_timezone}")
    print(f"DEBUG: reminder.when.tzinfo={reminder.when.tzinfo}")
    print(f"DEBUG: reminder.when type={type(reminder.when)}")
    
    utc_when = convert_from_timezone(reminder.when, user_timezone)
    print(f"DEBUG: Converted to UTC: {utc_when}")
    print(f"DEBUG: utc_when.tzinfo={utc_when.tzinfo}")
    
    db_reminder = Reminder(
        owner_id=current_user.id,
        when=utc_when,
        note=reminder.note
    )
    db.add(db_reminder)
    db.commit()
    db.refresh(db_reminder)
    print(f"DEBUG: Created reminder with ID {db_reminder.id}")
    print(f"DEBUG: Stored reminder when={db_reminder.when}")
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
    print(f"DEBUG: Getting today's reminders for user_timezone={user_timezone}")
    
    # Get current date in user's timezone
    tz = pytz.timezone(user_timezone)
    now = datetime.now(tz)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    print(f"DEBUG: Today in {user_timezone}: {today_start} to {today_end}")
    print(f"DEBUG: Current time in {user_timezone}: {now}")
    
    # Convert to UTC for database query
    utc_start = today_start.astimezone(pytz.UTC)
    utc_end = today_end.astimezone(pytz.UTC)
    
    # Convert to naive datetimes for SQLite compatibility (UTC)
    naive_utc_start = utc_start.replace(tzinfo=None)
    naive_utc_end = utc_end.replace(tzinfo=None)
    
    print(f"DEBUG: UTC range for query: {utc_start} to {utc_end}")
    print(f"DEBUG: Naive UTC range for query: {naive_utc_start} to {naive_utc_end}")
    
    reminders = db.query(Reminder).filter(
        Reminder.owner_id == current_user.id,
        Reminder.when >= naive_utc_start,
        Reminder.when <= naive_utc_end
    ).order_by(Reminder.when).all()
    
    print(f"DEBUG: Found {len(reminders)} reminders for today")
    for reminder in reminders:
        print(f"DEBUG: Reminder {reminder.id}: when={reminder.when}, note={reminder.note}")
        print(f"DEBUG: Reminder {reminder.id}: when type={type(reminder.when)}")
        print(f"DEBUG: Reminder {reminder.id}: when tzinfo={reminder.when.tzinfo}")
    
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
        # Convert the reminder time from user's timezone to UTC for storage
        user_timezone = current_user.timezone
        utc_when = convert_from_timezone(reminder_update.when, user_timezone)
        db_reminder.when = utc_when
    if reminder_update.note is not None:
        db_reminder.note = reminder_update.note
    
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
