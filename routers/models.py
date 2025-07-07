from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from models.models import Model
from models.user import User
from models.keys import Key
from schemas.models import ModelCreate, ModelUpdate, ModelResponse

router = APIRouter(prefix="/models", tags=["models"])

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

@router.post("/", response_model=ModelResponse)
def create_model(
    model: ModelCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new model"""
    # Check if model with this API key already exists
    existing_model = db.query(Model).filter(Model.api_key == model.api_key).first()
    if existing_model:
        raise HTTPException(status_code=400, detail="Model with this API key already exists")
    
    db_model = Model(
        api_key=model.api_key,
        owner=current_user.id,
        name=model.name,
        base_url=model.base_url
    )
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model

@router.get("/", response_model=List[ModelResponse])
def get_models(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all models for the authenticated user"""
    models = db.query(Model).filter(Model.owner == current_user.id).offset(skip).limit(limit).all()
    return models

@router.get("/{api_key}", response_model=ModelResponse)
def get_model(
    api_key: str, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific model by API key (only if owned by authenticated user)"""
    model = db.query(Model).filter(
        Model.api_key == api_key,
        Model.owner == current_user.id
    ).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.get("/id/{model_id}", response_model=ModelResponse)
def get_model_by_id(
    model_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific model by ID (only if owned by authenticated user)"""
    model = db.query(Model).filter(
        Model.id == model_id,
        Model.owner == current_user.id
    ).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model

@router.put("/{api_key}", response_model=ModelResponse)
def update_model(
    api_key: str, 
    model_update: ModelUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a model (only if owned by authenticated user)"""
    db_model = db.query(Model).filter(
        Model.api_key == api_key,
        Model.owner == current_user.id
    ).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    update_data = model_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    db.commit()
    db.refresh(db_model)
    return db_model

@router.put("/id/{model_id}", response_model=ModelResponse)
def update_model_by_id(
    model_id: int, 
    model_update: ModelUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update a model by ID (only if owned by authenticated user)"""
    db_model = db.query(Model).filter(
        Model.id == model_id,
        Model.owner == current_user.id
    ).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    update_data = model_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    
    db.commit()
    db.refresh(db_model)
    return db_model

@router.delete("/{api_key}")
def delete_model(
    api_key: str, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a model (only if owned by authenticated user)"""
    db_model = db.query(Model).filter(
        Model.api_key == api_key,
        Model.owner == current_user.id
    ).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(db_model)
    db.commit()
    return {"message": "Model deleted successfully"}

@router.delete("/id/{model_id}")
def delete_model_by_id(
    model_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a model by ID (only if owned by authenticated user)"""
    db_model = db.query(Model).filter(
        Model.id == model_id,
        Model.owner == current_user.id
    ).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(db_model)
    db.commit()
    return {"message": "Model deleted successfully"}
