from fastapi import APIRouter, HTTPException, Depends, Query, Header, Request, Form, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from core.database import get_db
from models.notes import Note
from models.tasks import Task
from models.user import User
from schemas.notes import NoteCreate, NoteResponse
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from core.auth import check_user_auth
from core.templates import templates
from core.timezone import convert_to_timezone
import os
from models.notes import NoteAttachment

UPLOAD_DIR = "uploads/notes"

router = APIRouter(prefix="/notes", tags=["notes"])

def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db)
) -> User:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    user = db.query(User).filter(User.keys.any(key=x_api_key)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    return user

@router.post("/", response_model=NoteResponse)
def create_note(
    note: NoteCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check task ownership
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    db_note = Note(
        when=note.when,
        task_id=note.task_id,
        content=note.content
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note

# Helper to get all descendant task ids

def get_descendant_task_ids(task: Task, db: Session) -> List[int]:
    ids = [task.id]
    children = db.query(Task).filter(Task.parent_task_id == task.id).all()
    for child in children:
        ids.extend(get_descendant_task_ids(child, db))
    return ids

@router.get("/task/{task_id}", response_model=List[NoteResponse])
def get_notes_for_task(
    task_id: int,
    skip: int = 0,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Check task ownership
    task = db.query(Task).filter(Task.id == task_id, Task.owner == current_user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    # Get all descendant task ids
    ids = get_descendant_task_ids(task, db)
    notes = db.query(Note).filter(Note.task_id.in_(ids)).order_by(Note.when.desc()).offset(skip).limit(limit).all()
    return notes

@router.get("/timeline")
def timeline(request: Request, task_id: int, page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    task = db.query(Task).filter(Task.id == task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    user = db.query(User).filter(User.id == user_id).first()
    user_tz = user.timezone if user and user.timezone else "Asia/Tehran"
    ids = get_descendant_task_ids(task, db)
    total_notes = db.query(Note).filter(Note.task_id.in_(ids)).count()
    notes_raw = db.query(Note).filter(Note.task_id.in_(ids)).order_by(Note.when.desc()).offset((page-1)*page_size).limit(page_size).all()
    notes = []
    from core.timezone import convert_to_timezone
    for note in notes_raw:
        attachments = []
        for att in note.attachments:
            uploaded_at_local = convert_to_timezone(att.uploaded_at, user_tz).strftime('%Y-%m-%d %H:%M') if att.uploaded_at else None
            attachments.append({
                "id": att.id,
                "filename": att.filename,
                "uploaded_at": att.uploaded_at,
                "uploaded_at_local": uploaded_at_local
            })
        notes.append({
            "id": note.id,
            "when": note.when,
            "when_local": convert_to_timezone(note.when, user_tz).strftime('%Y-%m-%d %H:%M'),
            "task_id": note.task_id,
            "content": note.content,
            "attachments": attachments
        })
    return templates.TemplateResponse("timeline.html", {"request": request, "notes": notes, "task": task, "page": page, "page_size": page_size, "total_notes": total_notes, "user": auth_info["user"], "user_tz": user_tz})

@router.get("/add-note")
def add_note_form(request: Request, task_id: int, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    task = db.query(Task).filter(Task.id == task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    return templates.TemplateResponse("add_note.html", {"request": request, "task": task, "user": auth_info["user"]})

@router.post("/add-note")
def add_note_submit(
    request: Request,
    task_id: int = Form(...),
    content: str = Form(...),
    attachments: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    task = db.query(Task).filter(Task.id == task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by user")
    note = Note(when=datetime.utcnow(), task_id=task_id, content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    # Handle file attachments
    if attachments:
        note_dir = os.path.join(UPLOAD_DIR, str(note.id))
        os.makedirs(note_dir, exist_ok=True)
        for file in attachments:
            if file.filename:
                file_path = os.path.join(note_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(file.file.read())
                attachment = NoteAttachment(note_id=note.id, filename=file.filename, filepath=file_path)
                db.add(attachment)
        db.commit()
    return RedirectResponse(url=f"/notes/timeline?task_id={task_id}", status_code=303)

@router.post("/delete-note/{note_id}")
@router.get("/delete-note/{note_id}")
def delete_note(request: Request, note_id: int, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Check task ownership
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=403, detail="Not authorized to delete this note")
    db.delete(note)
    db.commit()
    return RedirectResponse(url=f"/notes/timeline?task_id={task.id}", status_code=303)

@router.get("/edit-note/{note_id}")
def edit_note_form(request: Request, note_id: int, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Check task ownership
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=403, detail="Not authorized to edit this note")
    user = db.query(User).filter(User.id == user_id).first()
    user_tz = user.timezone if user and user.timezone else "Asia/Tehran"
    # Convert attachment times
    attachments = []
    from core.timezone import convert_to_timezone
    for att in note.attachments:
        uploaded_at_local = convert_to_timezone(att.uploaded_at, user_tz).strftime('%Y-%m-%d %H:%M') if att.uploaded_at else None
        attachments.append({
            "id": att.id,
            "filename": att.filename,
            "uploaded_at": att.uploaded_at,
            "uploaded_at_local": uploaded_at_local
        })
    note_dict = {
        "id": note.id,
        "content": note.content,
        "attachments": attachments
    }
    return templates.TemplateResponse("edit_note.html", {"request": request, "note": note_dict, "task": task, "user": auth_info["user"], "user_tz": user_tz})

@router.post("/edit-note/{note_id}")
def edit_note_submit(
    request: Request,
    note_id: int,
    content: str = Form(...),
    attachments: List[UploadFile] = File([]),
    db: Session = Depends(get_db)
):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Check task ownership
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=403, detail="Not authorized to edit this note")
    note.content = content
    db.commit()
    # Handle file attachments
    if attachments:
        note_dir = os.path.join(UPLOAD_DIR, str(note.id))
        os.makedirs(note_dir, exist_ok=True)
        for file in attachments:
            if file.filename:
                file_path = os.path.join(note_dir, file.filename)
                with open(file_path, "wb") as f:
                    f.write(file.file.read())
                attachment = NoteAttachment(note_id=note.id, filename=file.filename, filepath=file_path)
                db.add(attachment)
        db.commit()
    return RedirectResponse(url=f"/notes/timeline?task_id={task.id}", status_code=303)

@router.post("/upload-attachment/{note_id}")
def upload_attachment(note_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), request: Request = None):
    auth_info = check_user_auth(request, db) if request else None
    if auth_info and not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    # Ensure upload dir exists
    note_dir = os.path.join(UPLOAD_DIR, str(note_id))
    os.makedirs(note_dir, exist_ok=True)
    file_path = os.path.join(note_dir, file.filename)
    with open(file_path, "wb") as f:
        f.write(file.file.read())
    attachment = NoteAttachment(note_id=note_id, filename=file.filename, filepath=file_path)
    db.add(attachment)
    db.commit()
    return {"filename": file.filename, "url": f"/notes/download-attachment/{attachment.id}"}

@router.get("/download-attachment/{attachment_id}")
def download_attachment(attachment_id: int, db: Session = Depends(get_db)):
    attachment = db.query(NoteAttachment).filter(NoteAttachment.id == attachment_id).first()
    if not attachment or not os.path.exists(attachment.filepath):
        raise HTTPException(status_code=404, detail="Attachment not found")
    return FileResponse(attachment.filepath, filename=attachment.filename)

@router.post("/delete-attachment/{attachment_id}")
def delete_attachment(request: Request, attachment_id: int, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    attachment = db.query(NoteAttachment).filter(NoteAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    note = db.query(Note).filter(Note.id == attachment.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=403, detail="Not authorized to delete this attachment")
    # Remove file from disk
    if attachment.filepath and os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)
    db.delete(attachment)
    db.commit()
    return RedirectResponse(url=f"/notes/edit-note/{note.id}", status_code=303)

@router.get("/delete-attachment/{attachment_id}")
def delete_attachment_get(request: Request, attachment_id: int, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return RedirectResponse(url="/login", status_code=302)
    user_id = auth_info["user"]["id"]
    attachment = db.query(NoteAttachment).filter(NoteAttachment.id == attachment_id).first()
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    note = db.query(Note).filter(Note.id == attachment.note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    task = db.query(Task).filter(Task.id == note.task_id, Task.owner == user_id).first()
    if not task:
        raise HTTPException(status_code=403, detail="Not authorized to delete this attachment")
    # Remove file from disk
    if attachment.filepath and os.path.exists(attachment.filepath):
        os.remove(attachment.filepath)
    db.delete(attachment)
    db.commit()
    return RedirectResponse(url=f"/notes/edit-note/{note.id}", status_code=303)

@router.post("/upload-image")
def upload_image(request: Request, file: UploadFile = File(None), image: UploadFile = File(None), db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    if not auth_info["is_authenticated"]:
        return JSONResponse({"success": 0, "message": "Not authenticated"}, status_code=200)
    user_id = auth_info["user"]["id"]
    upload = file or image
    if not upload:
        return JSONResponse({"success": 0, "message": "No file uploaded"}, status_code=200)
    # Only allow image files
    if not upload.content_type.startswith("image/"):
        return JSONResponse({"success": 0, "message": "Only image files are allowed"}, status_code=200)
    # Save to uploads/notes/images/{user_id}/
    image_dir = os.path.join(UPLOAD_DIR, "images", str(user_id))
    os.makedirs(image_dir, exist_ok=True)
    filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}_{upload.filename}"
    file_path = os.path.join(image_dir, filename)
    with open(file_path, "wb") as f:
        f.write(upload.file.read())
    url = f"/notes/image/{user_id}/{filename}"
    return JSONResponse({"success": 1, "file": {"url": url}}, status_code=200)

@router.get("/image/{user_id}/{filename}")
def serve_note_image(user_id: int, filename: str):
    file_path = os.path.join(UPLOAD_DIR, "images", str(user_id), filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)

@router.get("/debug-delete-note/{note_id}")
def debug_delete_note(note_id: int):
    return {"msg": "Route works", "note_id": note_id} 