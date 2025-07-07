import pytz
from fastapi import APIRouter, HTTPException, Depends, Header, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from core.database import get_db
from models.activity import Activity, ActivityStatus
from models.user import User
from models.keys import Key
from models.tasks import Task
from schemas.activity import ActivityCreate, ActivityUpdate, ActivityResponse, ACTIVITY_STATUS_MAP, ActivityDetailsResponse
from core.timezone import convert_from_app_timezone, convert_to_timezone
from models.projects import Project
from pydantic import BaseModel

router = APIRouter(prefix="/activities", tags=["activities"])

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

def validate_activity_status(value: str) -> bool:
    """Validate activity status value"""
    return value in ["PLANNED", "DOING", "DONE"]

@router.post("/", response_model=List[ActivityResponse])
def create_activity(
    activity: ActivityCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new activity (or multiple recurring activities)"""
    # Validate that task exists and belongs to user
    task = db.query(Task).filter(
        Task.id == activity.task_id,
        Task.owner == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Prevent multiple DOING activities
    status_value = ACTIVITY_STATUS_MAP[activity.status.value]
    if status_value == "DOING":
        existing_doing = db.query(Activity).join(Task).filter(
            Task.owner == current_user.id,
            Activity.status == "DOING"
        ).first()
        if existing_doing:
            raise HTTPException(status_code=400, detail="You already have an active (DOING) activity. Please clock out before starting a new one.")
    # Validate status value
    if not validate_activity_status(status_value):
        raise HTTPException(status_code=400, detail="Invalid activity status value")
    
    # Validate recurring parameters if recurring is enabled
    if activity.is_recurring:
        if not activity.days_interval or activity.days_interval <= 0:
            raise HTTPException(status_code=400, detail="Days interval must be greater than 0 for recurring activities")
        if not activity.recurrence_count or activity.recurrence_count <= 0:
            raise HTTPException(status_code=400, detail="Recurrence count must be greater than 0 for recurring activities")
    
    # Convert times to UTC for storage
    clock_in_utc = convert_from_app_timezone(activity.clock_in)
    clock_out_utc = None
    if activity.clock_out:
        clock_out_utc = convert_from_app_timezone(activity.clock_out)
    
    # Validate clock_out is after clock_in if provided
    if clock_out_utc and clock_out_utc <= clock_in_utc:
        raise HTTPException(status_code=400, detail="Clock out time must be after clock in time")
    
    created_activities = []
    
    # Create the original activity
    db_activity = Activity(
        clock_in=clock_in_utc,
        clock_out=clock_out_utc,
        task_id=activity.task_id,
        status=status_value,
        description=activity.description
    )
    db.add(db_activity)
    db.flush()  # Get the ID without committing
    created_activities.append(db_activity)
    
    # Create recurring activities if enabled
    if activity.is_recurring and activity.days_interval and activity.recurrence_count:
        for i in range(1, activity.recurrence_count + 1):
            # Calculate the new clock_in time
            new_clock_in = clock_in_utc + timedelta(days=activity.days_interval * i)
            
            # Calculate the new clock_out time if it exists
            new_clock_out = None
            if clock_out_utc:
                new_clock_out = clock_out_utc + timedelta(days=activity.days_interval * i)
            
            # Create the recurring activity
            recurring_activity = Activity(
                clock_in=new_clock_in,
                clock_out=new_clock_out,
                task_id=activity.task_id,
                status=status_value,
                description=activity.description
            )
            db.add(recurring_activity)
            created_activities.append(recurring_activity)
    
    db.commit()
    
    # Refresh all created activities to get their IDs
    for activity_obj in created_activities:
        db.refresh(activity_obj)
    
    return created_activities

@router.get("/", response_model=List[ActivityResponse])
def get_activities(
    skip: int = 0, 
    limit: int = 100, 
    timezone: Optional[str] = Query(None, description="Timezone for date interpretation (e.g., Asia/Tehran)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all activities for the authenticated user"""
    activities = db.query(Activity).join(Task).filter(
        Task.owner == current_user.id
    ).offset(skip).limit(limit).all()
    
    # Convert times to user's timezone
    user_timezone = current_user.timezone or "UTC"
    for activity in activities:
        # Activities are stored in UTC (naive), so we need to localize them as UTC
        # and then convert to the selected timezone
        clock_in_utc = pytz.UTC.localize(activity.clock_in)
        activity.clock_in = clock_in_utc.astimezone(pytz.timezone(user_timezone))
        if activity.clock_out:
            clock_out_utc = pytz.UTC.localize(activity.clock_out)
            activity.clock_out = clock_out_utc.astimezone(pytz.timezone(user_timezone))
    
    return activities

@router.get("/date-range", response_model=List[ActivityDetailsResponse])
def get_activities_by_date_range(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    skip: int = Query(0, description="Number of records to skip"),
    limit: int = Query(50, description="Maximum number of records to return"),
    timezone: Optional[str] = Query(None, description="Timezone for date interpretation (e.g., Asia/Tehran)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all activities within a date range (only if owned by authenticated user)"""
    try:
        # Parse dates and make them timezone-aware in the specified timezone or user's timezone
        user_timezone = timezone or current_user.timezone or "UTC"
        print(f"DEBUG: Raw timezone parameter: {timezone}")
        print(f"DEBUG: User timezone from DB: {current_user.timezone}")
        print(f"DEBUG: Final timezone: {user_timezone}")
        print(f"DEBUG: Timezone parameter type: {type(timezone)}")
        print(f"DEBUG: Timezone parameter repr: {repr(timezone)}")
        print(f"DEBUG: Current user ID: {current_user.id}")
        print(f"DEBUG: Current user username: {current_user.username}")
        
        try:
            tz = pytz.timezone(user_timezone)
        except Exception as e:
            print(f"DEBUG: Error creating timezone object for {user_timezone}: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid timezone: {user_timezone}")
        
        # Create timezone-aware datetime objects for the start and end of the specified dates
        # We want the full day in the user's timezone
        start_dt = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = tz.localize(datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)) - timedelta(microseconds=1)
        
        # Since activities are stored in UTC (naive datetimes), we need to convert
        # the query range to UTC for comparison
        start_dt_utc = start_dt.astimezone(pytz.UTC)
        end_dt_utc = end_dt.astimezone(pytz.UTC)
        
        # Convert to naive datetimes for SQLite compatibility (UTC)
        start_dt_naive = start_dt_utc.replace(tzinfo=None)
        end_dt_naive = end_dt_utc.replace(tzinfo=None)
        
        # Debug logging
        print(f"DEBUG: User timezone: {user_timezone}")
        print(f"DEBUG: Start date string: {start_date}")
        print(f"DEBUG: End date string: {end_date}")
        print(f"DEBUG: Start datetime: {start_dt}")
        print(f"DEBUG: End datetime: {end_dt}")
        print(f"DEBUG: Start datetime naive: {start_dt_naive}")
        print(f"DEBUG: End datetime naive: {end_dt_naive}")
        
        # Validate date range
        if start_dt > end_dt:
            raise HTTPException(status_code=400, detail="Start date must be before end date")

        # Fetch all activities for the user that could possibly fall in the date range
        # Use a broad range to reduce the number of activities fetched
        possible_activities = db.query(Activity).join(Task).join(Project).filter(
            Task.owner == current_user.id,
            Activity.clock_in >= start_dt_naive - timedelta(days=1),  # buffer for TZ shifts
            Activity.clock_in <= end_dt_naive + timedelta(days=1)
        ).order_by(Activity.clock_in.desc()).all()

        filtered_activities = []
        for activity in possible_activities:
            # Activities are stored in UTC (naive), so we need to localize them as UTC
            # and then convert to the selected timezone for comparison
            try:
                # Localize the naive datetime as UTC
                clock_in_utc = pytz.UTC.localize(activity.clock_in)
                # Convert to selected timezone
                clock_in_tz = clock_in_utc.astimezone(tz)
                # Check if clock_in_tz falls within the selected date range in the selected timezone
                if start_dt <= clock_in_tz <= end_dt:
                    filtered_activities.append(activity)
            except Exception as e:
                print(f"DEBUG: Error processing activity {activity.id}: {e}")
                # Skip this activity if there's an error
                continue

        # Apply pagination
        paginated_activities = filtered_activities[skip:skip+limit]

        # Build the response as before
        response = []
        for activity in paginated_activities:
            task = db.query(Task).filter(Task.id == activity.task_id).first()
            project = db.query(Project).filter(Project.id == task.proj_id).first() if task else None
            
            # Convert times to the requested timezone for display
            # Activities are stored in UTC (naive), so we need to localize them as UTC
            # and then convert to the selected timezone
            clock_in_utc = pytz.UTC.localize(activity.clock_in)
            clock_in_tz = clock_in_utc.astimezone(tz)
            
            clock_out_tz = None
            if activity.clock_out:
                clock_out_utc = pytz.UTC.localize(activity.clock_out)
                clock_out_tz = clock_out_utc.astimezone(tz)
            
            response.append(ActivityDetailsResponse(
                id=activity.id,
                clock_in=clock_in_tz,
                clock_out=clock_out_tz,
                status=activity.status,
                description=activity.description,
                task_id=activity.task_id,
                task_name=task.title if task else None,
                project_id=project.id if project else None,
                project_name=project.name if project else None
            ))
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Exception in date-range endpoint: {e}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching activities: {str(e)}")

@router.get("/count", response_model=dict)
def get_activities_count(
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    timezone: Optional[str] = Query(None, description="Timezone for date interpretation (e.g., Asia/Tehran)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get the total count of activities for the authenticated user"""
    try:
        query = db.query(Activity).join(Task).filter(Task.owner == current_user.id)
        
        # Apply date filter if provided
        if start_date and end_date:
            # Parse dates and make them timezone-aware in the specified timezone or user's timezone
            user_timezone = timezone or current_user.timezone or "UTC"
            print(f"DEBUG: Count endpoint - Raw timezone parameter: {timezone}")
            print(f"DEBUG: Count endpoint - User timezone from DB: {current_user.timezone}")
            print(f"DEBUG: Count endpoint - Final timezone: {user_timezone}")
            print(f"DEBUG: Count endpoint - Timezone parameter type: {type(timezone)}")
            print(f"DEBUG: Count endpoint - Timezone parameter repr: {repr(timezone)}")
            print(f"DEBUG: Count endpoint - Current user ID: {current_user.id}")
            print(f"DEBUG: Count endpoint - Current user username: {current_user.username}")
            
            try:
                tz = pytz.timezone(user_timezone)
            except Exception as e:
                print(f"DEBUG: Count endpoint - Error creating timezone object for {user_timezone}: {e}")
                raise HTTPException(status_code=400, detail=f"Invalid timezone: {user_timezone}")
            
            # Create timezone-aware datetime objects for the start and end of the specified dates
            start_dt = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
            end_dt = tz.localize(datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)) - timedelta(microseconds=1)
            
            # Since activities are stored in UTC (naive datetimes), we need to convert
            # the query range to UTC for comparison
            start_dt_utc = start_dt.astimezone(pytz.UTC)
            end_dt_utc = end_dt.astimezone(pytz.UTC)
            
            # Convert to naive datetimes for SQLite compatibility (UTC)
            start_dt_naive = start_dt_utc.replace(tzinfo=None)
            end_dt_naive = end_dt_utc.replace(tzinfo=None)
            
            # Validate date range
            if start_dt > end_dt:
                raise HTTPException(status_code=400, detail="Start date must be before end date")
            
            # For count, we'll use the same filtering logic as the main endpoint
            # Fetch all activities and filter them in Python
            all_activities = query.all()
            count = 0
            for activity in all_activities:
                try:
                    # Activities are stored in UTC (naive), so we need to localize them as UTC
                    # and then convert to the selected timezone for comparison
                    clock_in_utc = pytz.UTC.localize(activity.clock_in)
                    # Convert to selected timezone
                    clock_in_tz = clock_in_utc.astimezone(tz)
                    # Check if clock_in_tz falls within the selected date range in the selected timezone
                    if start_dt <= clock_in_tz <= end_dt:
                        count += 1
                except Exception as e:
                    print(f"DEBUG: Error processing activity {activity.id} in count: {e}")
                    continue
            
            return {"count": count}
        
        count = query.count()
        return {"count": count}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        print(f"DEBUG: Exception in count endpoint: {e}")
        print(f"DEBUG: Exception type: {type(e)}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error counting activities: {str(e)}")

@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(
    activity_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific activity (only if owned by authenticated user)"""
    activity = db.query(Activity).join(Task).filter(
        Activity.id == activity_id,
        Task.owner == current_user.id
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Convert times to user's timezone
    user_timezone = current_user.timezone or "UTC"
    # Activities are stored in UTC (naive), so we need to localize them as UTC
    # and then convert to the selected timezone
    clock_in_utc = pytz.UTC.localize(activity.clock_in)
    activity.clock_in = clock_in_utc.astimezone(pytz.timezone(user_timezone))
    if activity.clock_out:
        clock_out_utc = pytz.UTC.localize(activity.clock_out)
        activity.clock_out = clock_out_utc.astimezone(pytz.timezone(user_timezone))
    
    return activity

@router.put("/{activity_id}", response_model=ActivityResponse)
def update_activity(
    activity_id: int, 
    activity_update: ActivityUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update an activity (only if owned by authenticated user)
    
    Supports partial updates - only send the fields you want to change.
    Examples:
    - Update only status: {"status": "DONE"}
    - Update only clock_out: {"clock_out": "2024-01-15T23:59:59"}
    - Update multiple fields: {"status": "DONE", "clock_out": "2024-01-15T23:59:59"}
    """
    activity = db.query(Activity).join(Task).filter(
        Activity.id == activity_id,
        Task.owner == current_user.id
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Update fields if provided
    update_data = activity_update.dict(exclude_unset=True)
    
    # Prevent multiple DOING activities on update
    if 'status' in update_data:
        status_value = ACTIVITY_STATUS_MAP[update_data['status'].value]
        if status_value == "DOING":
            existing_doing = db.query(Activity).join(Task).filter(
                Task.owner == current_user.id,
                Activity.status == "DOING",
                Activity.id != activity_id
            ).first()
            if existing_doing:
                raise HTTPException(status_code=400, detail="You already have an active (DOING) activity. Please clock out before starting a new one.")
    # Validate task if being updated
    if 'task_id' in update_data:
        task = db.query(Task).filter(
            Task.id == update_data['task_id'],
            Task.owner == current_user.id
        ).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
    # Convert and validate status if being updated
    if 'status' in update_data:
        status_value = ACTIVITY_STATUS_MAP[update_data['status'].value]
        if not validate_activity_status(status_value):
            raise HTTPException(status_code=400, detail="Invalid activity status value")
        update_data['status'] = status_value
    
    # Convert datetime fields from app timezone to UTC for storage
    if 'clock_in' in update_data:
        update_data['clock_in'] = convert_from_app_timezone(update_data['clock_in'])
    if 'clock_out' in update_data:
        update_data['clock_out'] = convert_from_app_timezone(update_data['clock_out'])
    
    # Validate clock_out is after clock_in if both are being updated
    if 'clock_in' in update_data and 'clock_out' in update_data:
        # Ensure both datetimes are timezone-aware for comparison
        from datetime import timezone
        clock_in_dt = update_data['clock_in']
        clock_out_dt = update_data['clock_out']
        
        # Make sure both are timezone-aware
        if clock_in_dt and clock_in_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_in_dt = clock_in_dt.replace(tzinfo=timezone.utc)
        if clock_out_dt and clock_out_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_out_dt = clock_out_dt.replace(tzinfo=timezone.utc)
            
        if clock_out_dt and clock_out_dt <= clock_in_dt:
            raise HTTPException(status_code=400, detail="Clock out time must be after clock in time")
    elif 'clock_out' in update_data and 'clock_in' not in update_data:
        # Ensure both datetimes are timezone-aware for comparison
        from datetime import timezone
        clock_out_dt = update_data['clock_out']
        clock_in_dt = activity.clock_in
        
        # Make sure both are timezone-aware
        if clock_out_dt and clock_out_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_out_dt = clock_out_dt.replace(tzinfo=timezone.utc)
        if clock_in_dt and clock_in_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_in_dt = clock_in_dt.replace(tzinfo=timezone.utc)
            
        if clock_out_dt and clock_out_dt <= clock_in_dt:
            raise HTTPException(status_code=400, detail="Clock out time must be after clock in time")
    elif 'clock_in' in update_data and 'clock_out' not in update_data:
        # Ensure both datetimes are timezone-aware for comparison
        from datetime import timezone
        clock_in_dt = update_data['clock_in']
        clock_out_dt = activity.clock_out
        
        # Make sure both are timezone-aware
        if clock_in_dt and clock_in_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_in_dt = clock_in_dt.replace(tzinfo=timezone.utc)
        if clock_out_dt and clock_out_dt.tzinfo is None:
            # Assume UTC if no timezone info
            clock_out_dt = clock_out_dt.replace(tzinfo=timezone.utc)
            
        if clock_out_dt and clock_out_dt <= clock_in_dt:
            raise HTTPException(status_code=400, detail="Clock out time must be after clock in time")
    
    try:
        for field, value in update_data.items():
            setattr(activity, field, value)
        
        db.commit()
        db.refresh(activity)
        
        # Convert times to user's timezone for response
        user_timezone = current_user.timezone or "UTC"
        # Activities are stored in UTC (naive), so we need to localize them as UTC
        # and then convert to the selected timezone
        clock_in_utc = pytz.UTC.localize(activity.clock_in)
        activity.clock_in = clock_in_utc.astimezone(pytz.timezone(user_timezone))
        if activity.clock_out:
            clock_out_utc = pytz.UTC.localize(activity.clock_out)
            activity.clock_out = clock_out_utc.astimezone(pytz.timezone(user_timezone))
        
        return activity
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating activity: {str(e)}")

@router.patch("/{activity_id}", response_model=ActivityResponse)
def patch_activity(
    activity_id: int, 
    activity_update: ActivityUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch an activity (partial update, only if owned by authenticated user)
    
    This is an alternative to PUT for partial updates. Both PUT and PATCH work the same way.
    Only send the fields you want to change.
    """
    return update_activity(activity_id, activity_update, current_user, db)

@router.delete("/{activity_id}")
def delete_activity(
    activity_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an activity (only if owned by authenticated user)"""
    activity = db.query(Activity).join(Task).filter(
        Activity.id == activity_id,
        Task.owner == current_user.id
    ).first()
    if activity is None:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    db.delete(activity)
    db.commit()
    return {"message": "Activity deleted successfully"}

@router.get("/my", response_model=List[ActivityResponse])
def get_my_activities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all activities owned by the authenticated user"""
    activities = db.query(Activity).join(Task).filter(
        Task.owner == current_user.id
    ).all()
    
    # Convert times to user's timezone
    user_timezone = current_user.timezone or "UTC"
    for activity in activities:
        activity.clock_in = convert_to_timezone(activity.clock_in, user_timezone)
        if activity.clock_out:
            activity.clock_out = convert_to_timezone(activity.clock_out, user_timezone)
    
    return activities

@router.get("/task/{task_id}", response_model=List[ActivityResponse])
def get_activities_by_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all activities for a specific task (only if task is owned by authenticated user)"""
    # First verify the task belongs to the user
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    activities = db.query(Activity).filter(
        Activity.task_id == task_id
    ).all()
    
    # Convert times to user's timezone
    user_timezone = current_user.timezone or "UTC"
    for activity in activities:
        # Activities are stored in UTC (naive), so we need to localize them as UTC
        # and then convert to the selected timezone
        clock_in_utc = pytz.UTC.localize(activity.clock_in)
        activity.clock_in = clock_in_utc.astimezone(pytz.timezone(user_timezone))
        if activity.clock_out:
            clock_out_utc = pytz.UTC.localize(activity.clock_out)
            activity.clock_out = clock_out_utc.astimezone(pytz.timezone(user_timezone))
    
    return activities
