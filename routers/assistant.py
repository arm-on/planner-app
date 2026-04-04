import json
from datetime import datetime, timedelta
from typing import AsyncIterator, Dict, List, Optional
from urllib.parse import urlparse

from core.crewai_env import disable_crewai_telemetry

disable_crewai_telemetry()

import httpx
from crewai import Agent, Crew, LLM, Process, Task
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.assistant_context import (
    build_compact_context,
    build_planner_snapshot,
    update_memory_after_response,
)
from core.database import get_db
from models.activity import Activity
from models.assistant_events import AssistantEvent
from models.assistant_memory import AssistantMemory
from models.keys import Key
from models.models import Model
from models.progress import Progress
from models.projects import Project
from models.reminders import Reminder
from models.tasks import Task as DbTask
from models.user import User

router = APIRouter()


class AssistantQuery(BaseModel):
    model_api_key: str
    system_prompt: str
    user_prompt: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    project_mode: str = "auto"
    focus_project_id: Optional[int] = None


class AssistantStreamQuery(BaseModel):
    model_api_key: str
    user_prompt: str
    system_prompt: str = ""
    conversation_history: Optional[List[Dict[str, str]]] = []
    agentic_mode: bool = True
    project_mode: str = "auto"
    focus_project_id: Optional[int] = None


class MemoryResetRequest(BaseModel):
    mode: str = "all"


class AssistantContextResponse(BaseModel):
    metrics: Dict[str, int]
    active_projects: List[Dict[str, object]]
    focused_projects: List[Dict[str, object]]
    urgent_tasks: List[Dict[str, object]]
    upcoming_tasks: List[Dict[str, object]]
    upcoming_reminders: List[Dict[str, object]]
    recent_activity: List[Dict[str, object]]
    smart_actions: List[str]
    keywords: List[str]
    project_mode: str = "auto"
    scope_project_ids: List[int] = []


class AssistantPlannerRequest(BaseModel):
    model_api_key: str
    horizon: str = "today"
    project_mode: str = "auto"
    focus_project_id: Optional[int] = None


class AssistantActionRequest(BaseModel):
    action_type: str
    task_id: Optional[int] = None
    project_id: Optional[int] = None
    title: Optional[str] = None
    note: Optional[str] = None
    deadline: Optional[datetime] = None
    reminder_when: Optional[datetime] = None
    duration_minutes: int = 90


class AssistantEventRequest(BaseModel):
    event_type: str
    source: str = "assistant"
    action_type: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, object]] = None


class AssistantEffectivenessResponse(BaseModel):
    window_days: int
    total_events: int
    suggested_actions: int
    action_attempts: int
    action_success: int
    action_failed: int
    completion_rate: int
    top_actions: List[Dict[str, object]]


def get_current_user(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> User:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")

    key_record = db.query(Key).filter(
        Key.key == x_api_key,
        Key.expires_at > datetime.utcnow(),
    ).first()

    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")

    return key_record.owner_user


def run_crewai_assistant(system_prompt: str, user_prompt: str, model: Model) -> str:
    llm = LLM(
        model=model.name,
        base_url=model.base_url,
        api_key=model.api_key,
        temperature=0.2,
    )

    assistant_agent = Agent(
        role="Personal Productivity Assistant",
        goal="Give practical, accurate planning help based on the user's request.",
        backstory=(
            "You are a concise assistant focused on actionable productivity plans, "
            "task prioritization, and time management."
        ),
        allow_delegation=False,
        llm=llm,
        verbose=False,
    )

    assistant_task = Task(
        description=("System instructions:\n{system_prompt}\n\n{user_prompt}"),
        expected_output=(
            "Markdown with sections: Situation, Priorities, Next 3 actions, and Timeboxing. "
            "Reference real task IDs/project names when possible."
        ),
        agent=assistant_agent,
    )

    crew = Crew(
        agents=[assistant_agent],
        tasks=[assistant_task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff(
        inputs={
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }
    )

    return getattr(result, "raw", str(result))


def _require_model_for_user(db: Session, user_id: int, model_api_key: str) -> Model:
    model = db.query(Model).filter(Model.api_key == model_api_key, Model.owner == user_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


def _find_or_create_progress(db: Session, user_id: int) -> Progress:
    progress = db.query(Progress).filter(Progress.owner == user_id).order_by(Progress.id.asc()).first()
    if progress:
        return progress
    progress = Progress(owner=user_id, unit="steps", value=0, max_value=1)
    db.add(progress)
    db.flush()
    return progress


def _find_default_project(db: Session, user_id: int) -> Optional[Project]:
    return (
        db.query(Project)
        .filter(Project.owner == user_id)
        .order_by(Project.id.asc())
        .first()
    )


def _log_assistant_event(
    db: Session,
    user_id: int,
    event_type: str,
    source: str = "assistant",
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    metadata: Optional[Dict[str, object]] = None,
) -> None:
    event = AssistantEvent(
        owner=user_id,
        event_type=(event_type or "unknown").strip().lower(),
        source=(source or "assistant").strip().lower(),
        action_type=(action_type.strip().lower() if action_type else None),
        status=(status.strip().lower() if status else None),
        payload=json.dumps(metadata or {}, ensure_ascii=True),
    )
    db.add(event)


def _choose_agent(user_prompt: str) -> tuple[str, str]:
    prompt = (user_prompt or "").lower()
    if any(k in prompt for k in ["schedule", "plan", "tomorrow", "today"]):
        return (
            "Planning Agent",
            "Create practical schedules and step-by-step execution plans.",
        )
    if any(k in prompt for k in ["analyze", "report", "trend", "productivity"]):
        return (
            "Analytics Agent",
            "Analyze user data and explain performance insights clearly.",
        )
    if any(k in prompt for k in ["advice", "improve", "focus", "motivation"]):
        return (
            "Advisor Agent",
            "Provide coaching advice with concrete and realistic recommendations.",
        )
    return (
        "General Assistant Agent",
        "Handle mixed requests with concise and useful productivity guidance.",
    )


async def _stream_openai_compatible_completion(
    model: Model,
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
) -> AsyncIterator[str]:
    def _extract_piece(chunk: Dict[str, object], kind: str) -> str:
        if kind == "ollama_chat":
            return (((chunk.get("message") or {}) if isinstance(chunk, dict) else {}).get("content") or "")

        choices = chunk.get("choices") if isinstance(chunk, dict) else None
        if not choices or not isinstance(choices, list):
            return ""
        choice = choices[0] if choices else {}
        if not isinstance(choice, dict):
            return ""

        if kind == "openai_chat":
            return (
                ((choice.get("delta") or {}).get("content") if isinstance(choice.get("delta"), dict) else None)
                or ((choice.get("message") or {}).get("content") if isinstance(choice.get("message"), dict) else None)
                or (choice.get("text") if isinstance(choice.get("text"), str) else "")
                or ""
            )
        return (
            (choice.get("text") if isinstance(choice.get("text"), str) else None)
            or ((choice.get("message") or {}).get("content") if isinstance(choice.get("message"), dict) else None)
            or ""
        )

    def _base_candidates(raw_base: str) -> List[str]:
        trimmed = (raw_base or "").strip().rstrip("/")
        if not trimmed:
            return []

        parsed = urlparse(trimmed)
        if not parsed.scheme:
            host = trimmed.lstrip("/")
            return [f"http://{host}", f"https://{host}"]

        if parsed.scheme == "http":
            return [trimmed, f"https://{trimmed[len('http://') :]}"]
        if parsed.scheme == "https":
            return [trimmed, f"http://{trimmed[len('https://') :]}"]
        return [trimmed]

    base = (model.base_url or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=400, detail="Model base_url is empty")
    bases = _base_candidates(base)

    auth_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model.api_key}",
    }

    prompt_text = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
    ollama_model = model.name.split("/")[-1] if "/" in model.name else model.name

    candidate_pool = []
    for candidate_base in bases:
        ollama_base = candidate_base[:-3] if candidate_base.endswith("/v1") else candidate_base
        openai_base = candidate_base if candidate_base.endswith("/v1") else f"{candidate_base}/v1"
        candidate_pool.extend(
            [
                {
                    "kind": "openai_chat",
                    "url": f"{candidate_base}/chat/completions",
                    "headers": auth_headers,
                    "payload": {
                        "model": model.name,
                        "messages": messages,
                        "temperature": temperature,
                        "stream": True,
                    },
                },
                {
                    "kind": "openai_completions",
                    "url": f"{candidate_base}/completions",
                    "headers": auth_headers,
                    "payload": {
                        "model": model.name,
                        "prompt": prompt_text,
                        "temperature": temperature,
                        "stream": True,
                    },
                },
                {
                    "kind": "openai_chat",
                    "url": f"{openai_base}/chat/completions",
                    "headers": auth_headers,
                    "payload": {
                        "model": model.name,
                        "messages": messages,
                        "temperature": temperature,
                        "stream": True,
                    },
                },
                {
                    "kind": "openai_completions",
                    "url": f"{openai_base}/completions",
                    "headers": auth_headers,
                    "payload": {
                        "model": model.name,
                        "prompt": prompt_text,
                        "temperature": temperature,
                        "stream": True,
                    },
                },
                {
                    "kind": "ollama_chat",
                    "url": f"{ollama_base}/api/chat",
                    "headers": {"Content-Type": "application/json"},
                    "payload": {
                        "model": ollama_model,
                        "messages": messages,
                        "stream": True,
                    },
                },
            ]
        )
    # Deduplicate candidate URLs while preserving order.
    seen_urls = set()
    candidates = []
    for candidate in candidate_pool:
        url = candidate["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        candidates.append(candidate)

    last_error = None
    attempt_errors = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(120.0, read=120.0),
        trust_env=False,
        follow_redirects=True,
    ) as client:
        for candidate in candidates:
            try:
                async with client.stream(
                    "POST",
                    candidate["url"],
                    json=candidate["payload"],
                    headers=candidate["headers"],
                ) as response:
                    if response.status_code == 404:
                        last_error = f"404 at {candidate['url']}"
                        attempt_errors.append(last_error)
                        continue
                    response.raise_for_status()

                    if candidate["kind"] in {"openai_chat", "openai_completions"}:
                        async for raw_line in response.aiter_lines():
                            if not raw_line:
                                continue
                            data = raw_line[5:].strip() if raw_line.startswith("data:") else raw_line.strip()
                            if not data:
                                continue
                            if data == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data)
                            except Exception:
                                continue
                            piece = _extract_piece(chunk, candidate["kind"])
                            if piece:
                                yield piece
                        return

                    if candidate["kind"] == "ollama_chat":
                        async for raw_line in response.aiter_lines():
                            if not raw_line:
                                continue
                            try:
                                chunk = json.loads(raw_line)
                            except Exception:
                                continue
                            piece = _extract_piece(chunk, "ollama_chat")
                            if piece:
                                yield piece
                            if chunk.get("done") is True:
                                break
                        return
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                attempt_errors.append(f"{candidate['url']} -> {last_error}")
                continue

    raise HTTPException(
        status_code=502,
        detail=(
            "Streaming failed: no compatible endpoint found for this model/base_url. "
            f"Last error: {last_error or 'unknown'}. "
            f"Tried: {' | '.join(attempt_errors[-4:]) if attempt_errors else 'no candidates'}"
        ),
    )


@router.post("/query")
async def query_assistant(
    query: AssistantQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _require_model_for_user(db, current_user.id, query.model_api_key)

    try:
        compact = build_compact_context(
            db=db,
            user_id=current_user.id,
            mode="assistant",
            user_prompt=query.user_prompt,
            incoming_history=query.conversation_history or [],
            project_mode=query.project_mode,
            focus_project_id=query.focus_project_id,
        )
        effective_prompt = (
            f"{compact['context_text']}\n\n"
            f"Context status: estimated tokens {compact['estimated_tokens']}. "
            f"{'Older content compacted.' if compact['compacted'] else 'No compaction applied.'}"
        )

        response_text = run_crewai_assistant(
            system_prompt=query.system_prompt,
            user_prompt=effective_prompt,
            model=model,
        )
        update_memory_after_response(
            db=db,
            memory=compact["memory_row"],
            merged_history=compact["merged_history"],
            user_prompt=query.user_prompt,
            assistant_response=response_text,
        )
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="assistant_response",
            source="chat",
            status="success",
            metadata={
                "agentic": False,
                "estimated_tokens": compact["estimated_tokens"],
                "compacted": compact["compacted"],
            },
        )
        db.commit()
        snapshot = compact.get("planner_snapshot", {})
        return {
            "response": response_text,
            "meta": {
                "estimated_tokens": compact["estimated_tokens"],
                "compacted": compact["compacted"],
                "matched_entities": snapshot.get("matched_entities_count", 0),
                "focused_projects": len(snapshot.get("focused_projects", [])),
                "project_mode": snapshot.get("project_mode", "auto"),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CrewAI error: {str(exc)}")


@router.post("/assistant/stream")
async def stream_assistant_response(
    query: AssistantStreamQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _require_model_for_user(db, current_user.id, query.model_api_key)

    compact = build_compact_context(
        db=db,
        user_id=current_user.id,
        mode="agentic" if query.agentic_mode else "assistant",
        user_prompt=query.user_prompt,
        incoming_history=query.conversation_history or [],
        project_mode=query.project_mode,
        focus_project_id=query.focus_project_id,
    )

    snapshot = compact.get("planner_snapshot", {})
    agent_name = "single-model"
    if query.agentic_mode:
        agent_name, agent_goal = _choose_agent(query.user_prompt)
        system_prompt = (
            f"You are {agent_name}. {agent_goal} "
            "Output markdown with: Situation, Priorities, Next 3 actions, Timeboxing."
        )
    else:
        system_prompt = (query.system_prompt or "").strip() or (
            "You are a practical planning assistant. Output markdown with: "
            "Situation, Priorities, Next 3 actions, Timeboxing."
        )

    effective_prompt = (
        f"{compact['context_text']}\n\n"
        f"Context status: estimated tokens {compact['estimated_tokens']}. "
        f"{'Older content compacted.' if compact['compacted'] else 'No compaction applied.'}"
    )

    async def event_stream() -> AsyncIterator[str]:
        meta = {
            "estimated_tokens": compact["estimated_tokens"],
            "compacted": compact["compacted"],
            "matched_entities": snapshot.get("matched_entities_count", 0),
            "focused_projects": len(snapshot.get("focused_projects", [])),
            "project_mode": snapshot.get("project_mode", query.project_mode),
            "agent_used": agent_name,
        }
        yield f"event: meta\ndata: {json.dumps(meta, ensure_ascii=True)}\n\n"

        collected: List[str] = []
        try:
            async for piece in _stream_openai_compatible_completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": effective_prompt},
                ],
                temperature=0.2,
            ):
                collected.append(piece)
                yield f"event: delta\ndata: {json.dumps({'text': piece}, ensure_ascii=True)}\n\n"

            final_text = "".join(collected).strip() or "No response."
            update_memory_after_response(
                db=db,
                memory=compact["memory_row"],
                merged_history=compact["merged_history"],
                user_prompt=query.user_prompt,
                assistant_response=final_text,
            )
            _log_assistant_event(
                db=db,
                user_id=current_user.id,
                event_type="assistant_response_stream",
                source="chat_stream",
                status="success",
                metadata={
                    "agentic": query.agentic_mode,
                    "project_mode": query.project_mode,
                },
            )
            db.commit()
            yield f"event: done\ndata: {json.dumps({'response': final_text}, ensure_ascii=True)}\n\n"
        except Exception as exc:
            db.rollback()
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)}, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/assistant/daily-briefing")
async def build_daily_briefing(
    payload: AssistantPlannerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _require_model_for_user(db, current_user.id, payload.model_api_key)
    snapshot = build_planner_snapshot(
        db=db,
        user_id=current_user.id,
        user_prompt="",
        project_mode=payload.project_mode,
        focus_project_id=payload.focus_project_id,
    )

    horizon = (payload.horizon or "today").strip().lower()
    hours = 24 if horizon == "today" else 72
    prompt = (
        f"{snapshot['context_block']}\n\n"
        f"Build a concise {horizon} command-center briefing for the next {hours} hours. "
        "Use exact task IDs and project names from the context. "
        "Include: 1) mission statement, 2) top priorities, 3) risk alerts, "
        "4) a timeboxed execution plan. "
        "Be explicit about what the user should do in the next 90 minutes."
    )
    system = (
        "You are the planning command center for a smart productivity app. "
        "Your briefings must be specific, realistic, and immediately executable. "
        "Avoid generic advice and tie all recommendations to planner entities."
    )
    try:
        response_text = run_crewai_assistant(system_prompt=system, user_prompt=prompt, model=model)
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="briefing_generated",
            source="daily_briefing",
            status="success",
            metadata={"horizon": horizon},
        )
        db.commit()
        return {
            "briefing": response_text,
            "meta": {
                "horizon": horizon,
                "focused_projects": len(snapshot.get("focused_projects", [])),
                "urgent_open_tasks": snapshot.get("metrics", {}).get("urgent_open_tasks", 0),
                "project_mode": snapshot.get("project_mode", "auto"),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CrewAI error: {str(exc)}")


@router.post("/assistant/recovery-plan")
async def build_recovery_plan(
    payload: AssistantPlannerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = _require_model_for_user(db, current_user.id, payload.model_api_key)
    snapshot = build_planner_snapshot(
        db=db,
        user_id=current_user.id,
        user_prompt="recovery overdue missed",
        project_mode=payload.project_mode,
        focus_project_id=payload.focus_project_id,
    )
    metrics = snapshot["metrics"]
    risk_score = min(
        100,
        (metrics.get("urgent_open_tasks", 0) * 15)
        + (max(metrics.get("open_tasks", 0) - metrics.get("done_tasks", 0), 0) * 2),
    )

    prompt = (
        f"{snapshot['context_block']}\n\n"
        f"Current risk score: {risk_score}/100.\n"
        "Create a recovery plan to get the user back on track this week. "
        "Include: what to pause, what to keep, and a day-by-day rescue plan. "
        "Add one anti-overcommit rule and the first rescue action to do immediately."
    )
    system = (
        "You are a crisis replanning specialist for personal productivity. "
        "Prioritize clarity, constraints, and realistic execution."
    )

    try:
        response_text = run_crewai_assistant(system_prompt=system, user_prompt=prompt, model=model)
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="recovery_generated",
            source="recovery_plan",
            status="success",
            metadata={"risk_score": risk_score},
        )
        db.commit()
        return {
            "recovery_plan": response_text,
            "meta": {
                "risk_score": risk_score,
                "urgent_open_tasks": metrics.get("urgent_open_tasks", 0),
                "project_mode": snapshot.get("project_mode", "auto"),
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CrewAI error: {str(exc)}")


@router.get("/assistant/context", response_model=AssistantContextResponse)
async def get_assistant_context(
    project_mode: str = "auto",
    focus_project_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    snapshot = build_planner_snapshot(
        db=db,
        user_id=current_user.id,
        user_prompt="",
        project_mode=project_mode,
        focus_project_id=focus_project_id,
    )
    return AssistantContextResponse(
        metrics=snapshot["metrics"],
        active_projects=snapshot["active_projects"],
        focused_projects=snapshot["focused_projects"],
        urgent_tasks=snapshot["urgent_tasks"],
        upcoming_tasks=snapshot["upcoming_tasks"],
        upcoming_reminders=snapshot["upcoming_reminders"],
        recent_activity=snapshot["recent_activity"],
        smart_actions=snapshot["smart_actions"],
        keywords=snapshot["keywords"],
        project_mode=snapshot.get("project_mode", "auto"),
        scope_project_ids=snapshot.get("scope_project_ids", []),
    )


@router.post("/assistant/actions")
async def run_assistant_action(
    payload: AssistantActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    action = (payload.action_type or "").strip().lower()
    if action not in {"create_task", "reschedule_task", "add_reminder", "start_focus_block"}:
        raise HTTPException(status_code=400, detail="Unsupported action type")

    if action == "create_task":
        title = (payload.title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="title is required")
        project = None
        if payload.project_id:
            project = (
                db.query(Project)
                .filter(Project.id == payload.project_id, Project.owner == current_user.id)
                .first()
            )
        if project is None:
            project = _find_default_project(db, current_user.id)
        if project is None:
            raise HTTPException(status_code=400, detail="Create a project first")

        progress = _find_or_create_progress(db, current_user.id)
        task = DbTask(
            owner=current_user.id,
            title=title,
            proj_id=project.id,
            is_important=True,
            is_urgent=False,
            energy_level=2,
            state="todo",
            deadline=payload.deadline,
            progress_id=progress.id,
            parent_task_id=None,
        )
        db.add(task)
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="action_executed",
            source="assistant_action",
            action_type="create_task",
            status="success",
            metadata={"project_id": project.id},
        )
        db.commit()
        db.refresh(task)
        return {"message": f"Task #{task.id} created", "task_id": task.id}

    if action == "reschedule_task":
        if not payload.task_id or not payload.deadline:
            raise HTTPException(status_code=400, detail="task_id and deadline are required")
        task = (
            db.query(DbTask)
            .filter(DbTask.id == payload.task_id, DbTask.owner == current_user.id)
            .first()
        )
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        task.deadline = payload.deadline
        if task.state in {"open"}:
            task.state = "todo"
        db.add(task)
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="action_executed",
            source="assistant_action",
            action_type="reschedule_task",
            status="success",
            metadata={"task_id": task.id},
        )
        db.commit()
        return {"message": f"Task #{task.id} rescheduled", "task_id": task.id}

    if action == "add_reminder":
        note = (payload.note or payload.title or "").strip()
        when = payload.reminder_when
        if not note or not when:
            raise HTTPException(status_code=400, detail="note and reminder_when are required")
        reminder = Reminder(owner_id=current_user.id, note=note, when=when.replace(tzinfo=None))
        db.add(reminder)
        _log_assistant_event(
            db=db,
            user_id=current_user.id,
            event_type="action_executed",
            source="assistant_action",
            action_type="add_reminder",
            status="success",
            metadata={"note_length": len(note)},
        )
        db.commit()
        db.refresh(reminder)
        return {"message": f"Reminder #{reminder.id} created", "reminder_id": reminder.id}

    # start_focus_block
    task: Optional[DbTask] = None
    if payload.task_id:
        task = (
            db.query(DbTask)
            .filter(DbTask.id == payload.task_id, DbTask.owner == current_user.id)
            .first()
        )
    if task is None:
        task = (
            db.query(DbTask)
            .filter(DbTask.owner == current_user.id, DbTask.state.in_(["open", "todo", "doing"]))
            .order_by(DbTask.is_urgent.desc(), DbTask.is_important.desc(), DbTask.deadline.asc())
            .first()
        )
    if task is None:
        raise HTTPException(status_code=400, detail="No active task available for focus block")

    existing_doing = (
        db.query(Activity)
        .join(DbTask, Activity.task_id == DbTask.id)
        .filter(DbTask.owner == current_user.id, Activity.status == "DOING")
        .first()
    )
    if existing_doing:
        raise HTTPException(status_code=400, detail="You already have a running focus block")

    now = datetime.utcnow().replace(tzinfo=None)
    focus_activity = Activity(
        task_id=task.id,
        clock_in=now,
        clock_out=now + timedelta(minutes=max(15, min(240, payload.duration_minutes))),
        status="DOING",
        description="Started from assistant quick action",
    )
    task.state = "doing"
    db.add(focus_activity)
    db.add(task)
    _log_assistant_event(
        db=db,
        user_id=current_user.id,
        event_type="action_executed",
        source="assistant_action",
        action_type="start_focus_block",
        status="success",
        metadata={"task_id": task.id, "duration_minutes": payload.duration_minutes},
    )
    db.commit()
    db.refresh(focus_activity)
    return {
        "message": f"Focus block started on task #{task.id}",
        "activity_id": focus_activity.id,
        "task_id": task.id,
    }


@router.post("/assistant/events")
async def track_assistant_event(
    payload: AssistantEventRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _log_assistant_event(
        db=db,
        user_id=current_user.id,
        event_type=payload.event_type,
        source=payload.source,
        action_type=payload.action_type,
        status=payload.status,
        metadata=payload.metadata,
    )
    db.commit()
    return {"message": "event tracked"}


@router.get("/assistant/effectiveness", response_model=AssistantEffectivenessResponse)
async def get_assistant_effectiveness(
    window_days: int = 14,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    window_days = max(1, min(60, window_days))
    since = datetime.utcnow() - timedelta(days=window_days)
    events = (
        db.query(AssistantEvent)
        .filter(AssistantEvent.owner == current_user.id, AssistantEvent.created_at >= since)
        .all()
    )

    total_events = len(events)
    suggested_actions = len([e for e in events if e.event_type == "suggested_action_clicked"])
    action_events = [e for e in events if e.event_type in {"action_executed", "action_attempted"}]
    action_attempts = len(action_events)
    action_success = len([e for e in action_events if e.status == "success" or e.event_type == "action_executed"])
    action_failed = len([e for e in action_events if e.status == "failed"])
    completion_rate = int(round((action_success / action_attempts) * 100)) if action_attempts else 0

    top_rows = (
        db.query(
            AssistantEvent.action_type,
            func.count(AssistantEvent.id).label("count"),
        )
        .filter(
            AssistantEvent.owner == current_user.id,
            AssistantEvent.created_at >= since,
            AssistantEvent.event_type.in_(["action_executed", "action_attempted"]),
            AssistantEvent.action_type.isnot(None),
        )
        .group_by(AssistantEvent.action_type)
        .order_by(func.count(AssistantEvent.id).desc())
        .limit(4)
        .all()
    )
    top_actions = [
        {"action_type": action_type, "count": int(count)}
        for action_type, count in top_rows
    ]

    return AssistantEffectivenessResponse(
        window_days=window_days,
        total_events=total_events,
        suggested_actions=suggested_actions,
        action_attempts=action_attempts,
        action_success=action_success,
        action_failed=action_failed,
        completion_rate=completion_rate,
        top_actions=top_actions,
    )


@router.post("/assistant-memory/reset")
async def reset_assistant_memory(
    payload: MemoryResetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mode = (payload.mode or "all").strip().lower()
    if mode not in {"all", "assistant", "agentic"}:
        raise HTTPException(status_code=400, detail="mode must be one of: all, assistant, agentic")

    query = db.query(AssistantMemory).filter(AssistantMemory.owner == current_user.id)
    if mode != "all":
        query = query.filter(AssistantMemory.mode == mode)

    deleted = query.delete(synchronize_session=False)
    db.commit()
    return {"message": "Assistant memory reset", "deleted": deleted, "mode": mode}
