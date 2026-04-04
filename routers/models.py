from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from urllib.parse import urlparse
import httpx
from pydantic import BaseModel
from core.database import get_db
from models.models import Model
from models.user import User
from models.keys import Key
from schemas.models import ModelCreate, ModelUpdate, ModelResponse

router = APIRouter(prefix="/models", tags=["models"])


class ModelConnectionTestRequest(BaseModel):
    model_api_key: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None

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


@router.post("/test-connection")
def test_model_connection(
    payload: ModelConnectionTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test model connectivity and endpoint compatibility."""
    model_row = None
    if payload.model_api_key:
        model_row = db.query(Model).filter(
            Model.api_key == payload.model_api_key,
            Model.owner == current_user.id
        ).first()
        if model_row is None:
            raise HTTPException(status_code=404, detail="Model not found")

    base_url = (payload.base_url or (model_row.base_url if model_row else "") or "").strip().rstrip("/")
    model_name = (payload.model_name or (model_row.name if model_row else "") or "").strip()
    model_api_key = (payload.api_key or (model_row.api_key if model_row else "") or "").strip()

    if not base_url:
        raise HTTPException(status_code=400, detail="base_url is required")
    if not model_name:
        raise HTTPException(status_code=400, detail="model_name is required")

    def _base_candidates(raw_base: str) -> List[str]:
        parsed = urlparse(raw_base)
        if not parsed.scheme:
            host = raw_base.lstrip("/")
            return [f"http://{host}", f"https://{host}"]
        if parsed.scheme == "http":
            return [raw_base, f"https://{raw_base[len('http://') :]}"]
        if parsed.scheme == "https":
            return [raw_base, f"http://{raw_base[len('https://') :]}"]
        return [raw_base]

    candidate_pool = []
    for base in _base_candidates(base_url):
        ollama_base = base[:-3] if base.endswith("/v1") else base
        openai_base = base if base.endswith("/v1") else f"{base}/v1"
        candidate_pool.extend([
            ("openai_chat", f"{base}/chat/completions"),
            ("openai_chat", f"{openai_base}/chat/completions"),
            ("openai_completions", f"{base}/completions"),
            ("openai_completions", f"{openai_base}/completions"),
            ("ollama_chat", f"{ollama_base}/api/chat"),
        ])

    # Keep order but avoid duplicate probes.
    seen = set()
    candidates = []
    for kind, url in candidate_pool:
        if url in seen:
            continue
        seen.add(url)
        candidates.append((kind, url))

    auth_headers = {"Content-Type": "application/json"}
    if model_api_key:
        auth_headers["Authorization"] = f"Bearer {model_api_key}"

    tried = []
    compatible = None

    with httpx.Client(timeout=httpx.Timeout(20.0), trust_env=False, follow_redirects=True) as client:
        for kind, url in candidates:
            try:
                if kind == "openai_chat":
                    payload_data = {
                        "model": model_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                        "stream": False
                    }
                elif kind == "openai_completions":
                    payload_data = {
                        "model": model_name,
                        "prompt": "ping",
                        "max_tokens": 1,
                        "stream": False
                    }
                else:
                    payload_data = {
                        "model": model_name.split("/")[-1] if "/" in model_name else model_name,
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": False
                    }

                headers = {"Content-Type": "application/json"} if kind == "ollama_chat" else auth_headers
                response = client.post(url, headers=headers, json=payload_data)
                status = response.status_code
                tried.append({"kind": kind, "url": url, "status": status})

                if status in (200, 201):
                    compatible = {
                        "kind": kind,
                        "url": url,
                        "status": status,
                        "health": "ok"
                    }
                    break
                if status in (400, 401, 403, 422):
                    compatible = {
                        "kind": kind,
                        "url": url,
                        "status": status,
                        "health": "reachable"
                    }
                    break
            except Exception as exc:
                tried.append({"kind": kind, "url": url, "error": f"{type(exc).__name__}: {exc}"})

    if not compatible:
        return {
            "ok": False,
            "message": "No compatible endpoint found",
            "tried": tried
        }

    return {
        "ok": True,
        "message": "Compatible endpoint found",
        "compatible": compatible,
        "tried": tried
    }

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
