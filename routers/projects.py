from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from models.projects import Project
from models.user import User
from models.keys import Key
from schemas.projects import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])

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

@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project"""
    db_project = Project(
        owner=current_user.id,
        name=project.name,
        color=project.color
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

@router.get("/", response_model=List[ProjectResponse])
def get_projects(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all projects for the authenticated user"""
    projects = db.query(Project).filter(
        Project.owner == current_user.id
    ).offset(skip).limit(limit).all()
    return projects

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific project (only if owned by authenticated user)"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner == current_user.id
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int, 
    project_update: ProjectUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a project (only if owned by authenticated user)
    
    Supports partial updates - only send the fields you want to change.
    Examples:
    - Update only name: {"name": "New Project Name"}
    - Update only color: {"color": "#FF5733"}
    - Update both fields: {"name": "New Name", "color": "#33FF57"}
    """
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner == current_user.id
    ).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Update fields if provided
    update_data = project_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_project, field, value)
    
    db.commit()
    db.refresh(db_project)
    return db_project

@router.patch("/{project_id}", response_model=ProjectResponse)
def patch_project(
    project_id: int, 
    project_update: ProjectUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Patch a project (partial update, only if owned by authenticated user)
    
    This is an alternative to PUT for partial updates. Both PUT and PATCH work the same way.
    Only send the fields you want to change.
    """
    return update_project(project_id, project_update, current_user, db)

@router.delete("/{project_id}")
def delete_project(
    project_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project (only if owned by authenticated user)"""
    from models.tasks import Task
    from models.activity import Activity
    
    db_project = db.query(Project).filter(
        Project.id == project_id,
        Project.owner == current_user.id
    ).first()
    if db_project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    
    try:
        # Get all tasks associated with this project
        project_tasks = db.query(Task).filter(Task.proj_id == project_id).all()
        
        # Delete all activities associated with these tasks
        for task in project_tasks:
            task_activities = db.query(Activity).filter(Activity.task_id == task.id).all()
            for activity in task_activities:
                db.delete(activity)
        
        # Delete all tasks associated with this project
        for task in project_tasks:
            db.delete(task)
        
        # Delete the project
        db.delete(db_project)
        db.commit()
        
        return {"message": "Project and all associated tasks and activities deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")
