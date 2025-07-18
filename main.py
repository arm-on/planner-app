from fastapi import FastAPI, Request, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime, date, timezone
from typing import Optional
from pydantic import BaseModel
from core.date import DateResponse, format_date_helper
from routers import date
from routers import user as user_router
from routers import models as models_router
from routers import progress as progress_router
from routers import projects as projects_router
from routers import tasks as tasks_router
from routers import activity as activity_router
from routers import reports as reports_router
from routers import reminders as reminders_router
from routers import assistant as assistant_router
from routers.notes import router as notes_router
from core.database import engine, Base, get_db
from models import user, projects, models, keys, tasks, progress, reminders
from sqlalchemy.orm import Session
from datetime import datetime as dt
from core.auth import check_user_auth
import markdown2
from core.templates import templates

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI instance
app = FastAPI()

# Optional: Serve static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

# include routers
app.include_router(date.router)
app.include_router(user_router.router)
app.include_router(models_router.router)
app.include_router(progress_router.router)
app.include_router(projects_router.router)
app.include_router(tasks_router.router)
app.include_router(activity_router.router)
app.include_router(reports_router.router)
app.include_router(reminders_router.router)
app.include_router(assistant_router.router)
app.include_router(notes_router)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    auth_info = check_user_auth(request, db)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "is_authenticated": auth_info["is_authenticated"],
        "user": auth_info["user"]
    })

@app.get("/hello/{name}", response_class=HTMLResponse)
async def hello_name(request: Request, name: str):
    return templates.TemplateResponse("hello.html", {"request": request, "message": f"Hello {name}"})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/kanban", response_class=HTMLResponse)
async def kanban_page(request: Request):
    return templates.TemplateResponse("kanban.html", {"request": request})

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    return templates.TemplateResponse("report.html", {"request": request})

@app.get("/assistant", response_class=HTMLResponse)
async def assistant_page(request: Request):
    return templates.TemplateResponse("assistant.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
