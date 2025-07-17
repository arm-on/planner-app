from fastapi import APIRouter, HTTPException, Depends, Header, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from models.tasks import Task, EnergyLevel, TaskState
from models.user import User
from models.keys import Key
from models.projects import Project
from models.progress import Progress
from models.activity import Activity
from schemas.tasks import TaskCreate, TaskUpdate, TaskResponse, ENERGY_LEVEL_MAP, TASK_STATE_MAP

router = APIRouter(prefix="/tasks", tags=["tasks"])

def validate_energy_level(value: int) -> bool:
    """Validate energy level value"""
    return value in [1, 2, 3]

def validate_task_state(value: str) -> bool:
    """Validate task state value"""
    return value in ["open", "todo", "doing", "done", "closed"]

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

@router.post("/", response_model=TaskResponse)
def create_task(
    task: TaskCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new task"""
    # Validate that project exists and belongs to user
    project = db.query(Project).filter(
        Project.id == task.proj_id,
        Project.owner == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate that progress item exists and belongs to user
    progress = db.query(Progress).filter(
        Progress.id == task.progress_id,
        Progress.owner == current_user.id
    ).first()
    if not progress:
        raise HTTPException(status_code=404, detail="Progress item not found")
    
    # Validate parent task if provided
    if task.parent_task_id:
        parent_task = db.query(Task).filter(
            Task.id == task.parent_task_id,
            Task.owner == current_user.id
        ).first()
        if not parent_task:
            raise HTTPException(status_code=404, detail="Parent task not found")
    
    # Validate enum values
    energy_level_value = ENERGY_LEVEL_MAP[task.energy_level.value]
    state_value = TASK_STATE_MAP[task.state.value]
    
    if not validate_energy_level(energy_level_value):
        raise HTTPException(status_code=400, detail="Invalid energy level value")
    if not validate_task_state(state_value):
        raise HTTPException(status_code=400, detail="Invalid task state value")
    
    db_task = Task(
        owner=current_user.id,
        title=task.title,
        proj_id=task.proj_id,
        is_important=task.is_important,
        is_urgent=task.is_urgent,
        energy_level=energy_level_value,
        state=state_value,
        deadline=task.deadline,
        progress_id=task.progress_id,
        parent_task_id=task.parent_task_id
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.get("/", response_model=List[TaskResponse])
def get_tasks(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tasks for the authenticated user"""
    tasks = db.query(Task).options(
        joinedload(Task.progress)
    ).filter(
        Task.owner == current_user.id
    ).offset(skip).limit(limit).all()
    return tasks

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific task (only if owned by authenticated user)"""
    task = db.query(Task).options(
        joinedload(Task.progress)
    ).filter(
        Task.id == task_id,
        Task.owner == current_user.id
    ).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int, 
    task_update: TaskUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a task (only if owned by authenticated user)
    
    Supports partial updates - only send the fields you want to change.
    Examples:
    - Update only title: {"title": "New Task Title"}
    - Update only state: {"state": "done"}
    - Update multiple fields: {"title": "New Title", "state": "doing", "is_important": true}
    """
    db_task = db.query(Task).options(
        joinedload(Task.progress)
    ).filter(
        Task.id == task_id,
        Task.owner == current_user.id
    ).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Update fields if provided
    update_data = task_update.dict(exclude_unset=True)
    
    # Validate project if being updated
    if 'proj_id' in update_data:
        project = db.query(Project).filter(
            Project.id == update_data['proj_id'],
            Project.owner == current_user.id
        ).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate progress item if being updated
    if 'progress_id' in update_data:
        progress = db.query(Progress).filter(
            Progress.id == update_data['progress_id'],
            Progress.owner == current_user.id
        ).first()
        if not progress:
            raise HTTPException(status_code=404, detail="Progress item not found")
    
    # Validate parent task if being updated
    if 'parent_task_id' in update_data and update_data['parent_task_id']:
        parent_task = db.query(Task).filter(
            Task.id == update_data['parent_task_id'],
            Task.owner == current_user.id
        ).first()
        if not parent_task:
            raise HTTPException(status_code=404, detail="Parent task not found")
    
    # Convert and validate enum values if provided
    if 'energy_level' in update_data:
        energy_level_value = ENERGY_LEVEL_MAP[update_data['energy_level'].value]
        if not validate_energy_level(energy_level_value):
            raise HTTPException(status_code=400, detail="Invalid energy level value")
        update_data['energy_level'] = energy_level_value
    if 'state' in update_data:
        state_value = TASK_STATE_MAP[update_data['state'].value]
        if not validate_task_state(state_value):
            raise HTTPException(status_code=400, detail="Invalid task state value")
        update_data['state'] = state_value
    
    for field, value in update_data.items():
        setattr(db_task, field, value)
    
    db.commit()
    db.refresh(db_task)
    return db_task

@router.patch("/{task_id}", response_model=TaskResponse)
def patch_task(
    task_id: int, 
    task_update: TaskUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch a task (partial update, only if owned by authenticated user)
    
    This is an alternative to PUT for partial updates. Both PUT and PATCH work the same way.
    Only send the fields you want to change.
    """
    return update_task(task_id, task_update, current_user, db)

@router.delete("/{task_id}")
def delete_task(
    task_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a task and all associated data (only if owned by authenticated user)"""
    db_task = db.query(Task).filter(
        Task.id == task_id,
        Task.owner == current_user.id
    ).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        # Delete all activities associated with this task
        activities = db.query(Activity).filter(Activity.task_id == task_id).all()
        for activity in activities:
            db.delete(activity)
        
        # Get the progress record before deleting the task
        progress_id = db_task.progress_id
        
        # Delete the task
        db.delete(db_task)
        
        # Delete the associated progress record
        progress = db.query(Progress).filter(Progress.id == progress_id).first()
        if progress:
            db.delete(progress)
        
        db.commit()
        return {"message": "Task and all associated data deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete task: {str(e)}")

@router.get("/project/{project_id}", response_model=List[TaskResponse])
def get_tasks_by_project(
    project_id: int,
    skip: int = 0,
    limit: int = 100,
    all: bool = Query(False, description="If true, return all tasks for the project regardless of pagination or state."),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all tasks for a specific project (only if project is owned by authenticated user)"""
    # First verify the project belongs to the user
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner == current_user.id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    query = db.query(Task).options(
        joinedload(Task.progress)
    ).filter(
        Task.proj_id == project_id,
        Task.owner == current_user.id
    )
    if not all:
        query = query.filter(Task.state.notin_(["done", "closed"]))
        tasks = query.offset(skip).limit(limit).all()
    else:
        tasks = query.all()
    return tasks
