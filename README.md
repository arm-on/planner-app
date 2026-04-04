# Planner App

Smart time management and productivity workspace built with FastAPI, SQLite, and a modern self-hosted frontend.

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688.svg)
![SQLite](https://img.shields.io/badge/Database-SQLite-003B57.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [AI Assistant Setup (CrewAI + Local/Ollama)](#ai-assistant-setup-crewai--localollama)
- [Run the App](#run-the-app)
- [Core Routes](#core-routes)
- [Database Behavior](#database-behavior)
- [Troubleshooting](#troubleshooting)
- [Security Notes](#security-notes)
- [License](#license)

---

## Overview

**Planner App** is a full-featured personal productivity system designed for practical daily use:

- plan and track activities
- manage projects and tasks
- monitor progress and reports
- work with reminders and note timelines
- use an AI assistant grounded in your planner data

The UI includes a responsive top navigation, dark/light theme support, Kanban board, reporting dashboard, and AI assistant streaming responses.

---

## Key Features

### Productivity Core
- Activity scheduling (planned / doing / done), tracking, and date-range filtering
- Projects, tasks, and progress entities with CRUD operations
- Reminders with timezone-aware "today" and date-range retrieval
- Calendar view with upcoming planned activity section
- Kanban board for task flow
- Reports for time spent analysis

### Assistant + Intelligence
- Assistant streaming endpoint (`/assistant/stream`)
- Context-aware responses using project/task/activity snapshot
- Memory and compaction support for long conversations
- Daily briefing and recovery-plan endpoints
- Action/event/effectiveness telemetry endpoints (app-level)
- Model connection tester for endpoint diagnostics (`/models/test-connection`)

### Notes System
- Notes timeline per task
- Rich text editing with self-hosted CKEditor
- Image and attachment uploads/downloads
- Direction-aware Persian/English rendering (`dir="auto"` handling)

### UX
- Responsive UI (desktop/mobile)
- Collapsible mobile top menu
- Light + dark themes
- Fully self-hosted frontend vendor assets (Bootstrap, icons, CKEditor, Chart.js, etc.)

---

## Tech Stack

**Backend**
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- Uvicorn

**Frontend**
- Jinja2 templates
- Bootstrap (self-hosted)
- Vanilla JavaScript
- Custom CSS theme system

**AI**
- CrewAI
- OpenAI-compatible and Ollama-compatible endpoints

---

## Project Structure

```text
planner-app/
├── core/                # DB, auth, timezone, assistant context, compatibility patches
├── models/              # SQLAlchemy ORM models
├── routers/             # FastAPI route modules
├── schemas/             # Pydantic schemas
├── static/              # CSS, JS, self-hosted vendor assets
├── templates/           # Jinja2 HTML templates
├── uploads/             # Uploaded files (notes attachments/images)
├── main.py              # Application entrypoint
├── requirements.txt
└── test.db              # SQLite DB (auto-created if missing)
```

---

## Quick Start

### 1) Clone

```bash
git clone https://github.com/armanmalekzadeh/planner-app.git
cd planner-app
```

### 2) Create virtual environment

macOS/Linux:
```bash
python3 -m venv planner-app-env
source planner-app-env/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv planner-app-env
.\planner-app-env\Scripts\Activate.ps1
```

### 3) Install dependencies

```bash
pip install -r requirements.txt
```

---

## Configuration

This project currently uses default in-code configuration for SQLite:

- `core/database.py`:
  - `SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"`

No `.env` is required for basic local startup.

---

## AI Assistant Setup (CrewAI + Local/Ollama)

You can configure models from the UI (**Dashboard -> Models**).

Recommended local setup when app and Ollama are on the same machine:

- `base_url`: `http://127.0.0.1:11434/v1`
- `model_name`: e.g. `openai/gpt-oss:20b`
- `api_key`: any non-empty string for local gateways that require a field

Why `127.0.0.1`?
- It avoids DNS/NAT/firewall inconsistencies across machines.
- It is the most reliable setting for same-host app+LLM deployments (especially on Windows servers).

Use **Test Connection** in the Models modal to verify endpoint compatibility before chatting.

---

## Run the App

### Recommended (development with reload)

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

Then open:
- `http://localhost:9000`

### Alternative (without explicit uvicorn args)

```bash
python main.py
```

This runs on port `8000` as defined in `main.py`.

---

## Core Routes

High-level route groups:

- `/users/*` - registration, login, profile, keys, timezone
- `/models/*` - model CRUD + `/models/test-connection`
- `/projects/*` - project CRUD
- `/tasks/*` - task CRUD
- `/progress/*` - progress CRUD
- `/activities/*` - activity CRUD, counts, date-range
- `/reminders/*` - reminder CRUD, `today`, date-range
- `/reports/*` - report endpoints
- `/assistant/*` and `/query` - AI assistant, streaming, memory/events/effectiveness
- `/agentic-query` - alternate assistant flow
- `/notes/*` - notes timeline/editor/uploads

Interactive docs:
- `http://localhost:9000/docs`

---

## Database Behavior

If `test.db` does not exist:

- SQLite file is auto-created at startup.
- Tables are auto-created via:
  - `Base.metadata.create_all(bind=engine)` in `main.py`.

This means first boot works without a pre-made DB, but starts empty (no users/projects/tasks/models).

Important:
- The path is relative (`./test.db`) to your process working directory.
- Running from different directories can create different DB files unintentionally.

---

## Troubleshooting

### 1) Assistant fails with `502` / `no compatible endpoint`

Use **Dashboard -> Models -> Test Connection**.

Common causes:
- wrong host/port
- HTTP/HTTPS mismatch
- firewall or NAT rules
- model endpoint not listening

### 2) Windows server: `WinError 10061` / connection refused

If app and Ollama are on the same Windows host, use:
- `http://127.0.0.1:11434/v1`

instead of public domain-based URLs.

### 3) Dependency conflict after reinstalling AI packages

If FastAPI/Starlette/AnyIO mismatch appears, reinstall pinned versions from `requirements.txt`:

```bash
pip install -r requirements.txt --upgrade --force-reinstall
```

### 4) Port already in use

Use another port:

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 9010 --reload
```

### 5) Missing DB or data appears "gone"

Confirm current working directory and where `test.db` is being created.

---

## Security Notes

This repository is currently optimized for local/private deployments and rapid iteration.

- Passwords are stored directly in current user router logic (development-style).
- API keys are local app keys with expiration.
- Before public production deployment, add:
  - password hashing (bcrypt/argon2)
  - stricter auth/session hardening
  - HTTPS termination and secure headers
  - role-based permission checks and audit policies

---

## License

MIT License. See `LICENSE`.

---

## Author

Designed and developed by **Arman Malekzadeh**.
