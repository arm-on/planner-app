from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, date, timezone, timedelta
from core.database import get_db
from models.activity import Activity
from models.tasks import Task
from models.projects import Project
from models.user import User
from core.user import get_current_user
from core.timezone import convert_to_timezone
import pytz

router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/time-spent")
async def get_time_spent_report(
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    timezone: Optional[str] = Query(None, description="Timezone for date interpretation (e.g., Asia/Tehran)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a time spent report for the specified date range.
    Returns data for both project-level and task-level analysis.
    """
    try:
        # Parse dates and make them timezone-aware in the specified timezone or user's timezone
        user_timezone = timezone or current_user.timezone or "Asia/Tehran"
        tz = pytz.timezone(user_timezone)
        
        # Create timezone-aware datetime objects for the start and end of the specified dates
        start_dt = tz.localize(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = tz.localize(datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)) - timedelta(microseconds=1)
        
        # Convert to UTC for database comparison since activities are stored in UTC
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
        
        # Get all activities in the date range for the current user
        # Include activities that:
        # 1. Started within the date range, OR
        # 2. Ended within the date range, OR
        # 3. Started before and ended after the date range (spans the entire range)
        activities = db.query(Activity).join(Task).filter(
            Task.owner == current_user.id,
            Activity.status == "DONE",  # Only completed activities
            Activity.clock_out.isnot(None),  # Must have clock out time
            # Activity overlaps with the date range
            (
                (Activity.clock_in >= start_dt_naive) & (Activity.clock_in <= end_dt_naive) |  # Started within range
                (Activity.clock_out >= start_dt_naive) & (Activity.clock_out <= end_dt_naive) |  # Ended within range
                (Activity.clock_in <= start_dt_naive) & (Activity.clock_out >= end_dt_naive)  # Spans entire range
            )
        ).all()
        
        print(f"DEBUG: Found {len(activities)} activities in date range")
        for activity in activities:
            print(f"DEBUG: Activity {activity.id}: clock_in={activity.clock_in}, status={activity.status}")
        
        # Initialize data structures
        project_data = {}
        task_data = {}
        total_hours = 0
        total_activities = len(activities)
        
        # Process each activity
        for activity in activities:
            # Get the task for this activity
            task = db.query(Task).filter(Task.id == activity.task_id).first()
            if not task:
                continue
            
            # Convert activity times to user's timezone for accurate duration calculation
            clock_in_tz = convert_to_timezone(activity.clock_in, user_timezone)
            clock_out_tz = convert_to_timezone(activity.clock_out, user_timezone)
            
            # For activities that end on the specified date, count the full duration
            # This is especially important for activities like sleeping that span midnight
            if clock_out_tz.date() == start_dt.date():
                # Activity ends on the specified date - count full duration
                duration_hours = (clock_out_tz - clock_in_tz).total_seconds() / 3600
            else:
                # Activity doesn't end on the specified date - count only the portion within the date range
                effective_start = max(clock_in_tz, start_dt)
                effective_end = min(clock_out_tz, end_dt)
                duration_hours = (effective_end - effective_start).total_seconds() / 3600
            
            # Skip activities with zero or negative duration
            if duration_hours <= 0:
                continue
            
            total_hours += duration_hours
            
            # Aggregate by project
            project_id = task.proj_id
            if project_id not in project_data:
                project_data[project_id] = {
                    "total_hours": 0,
                    "activity_count": 0,
                    "project_name": "Unknown Project"
                }
            
            project_data[project_id]["total_hours"] += duration_hours
            project_data[project_id]["activity_count"] += 1
            
            # Get project name
            project = db.query(Project).filter(Project.id == project_id).first()
            if project:
                project_data[project_id]["project_name"] = project.name
            
            # Aggregate by task
            task_id = task.id
            if task_id not in task_data:
                task_data[task_id] = {
                    "total_hours": 0,
                    "activity_count": 0,
                    "task_name": task.title,
                    "project_id": project_id,
                    "project_name": project_data[project_id]["project_name"]
                }
            
            task_data[task_id]["total_hours"] += duration_hours
            task_data[task_id]["activity_count"] += 1
        
        # Round hours to 2 decimal places
        total_hours = round(total_hours, 2)
        for project_id in project_data:
            project_data[project_id]["total_hours"] = round(project_data[project_id]["total_hours"], 2)
        for task_id in task_data:
            task_data[task_id]["total_hours"] = round(task_data[task_id]["total_hours"], 2)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_hours": total_hours,
            "total_activities": total_activities,
            "project_data": project_data,
            "task_data": task_data
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}") 