import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models.activity import Activity
from models.assistant_memory import AssistantMemory
from models.projects import Project
from models.reminders import Reminder
from models.tasks import Task as DbTask

MAX_HISTORY_ITEMS = 14
MAX_CONTEXT_CHARS = 14000
COMPACT_TARGET_CHARS = 9500


def _safe_json_loads(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _estimate_tokens(text: str) -> int:
    # Rough estimate used only for guardrails; no tokenizer dependency required.
    return max(1, len(text) // 4)


def _summarize_turns(turns: List[Dict[str, str]], max_chars: int = 1800) -> str:
    if not turns:
        return ""

    lines: List[str] = []
    for item in turns:
        role = item.get("role", "user").strip().lower()
        content = " ".join((item.get("content") or "").split())
        if not content:
            continue
        label = "U" if role == "user" else "A"
        lines.append(f"{label}: {content[:220]}")
        if sum(len(x) for x in lines) > max_chars:
            break

    result = "\n".join(lines)
    return result[:max_chars]


def _compact_prompt(prompt: str, max_chars: int = 6000) -> str:
    clean = prompt.strip()
    if len(clean) <= max_chars:
        return clean

    head = clean[:2200]
    tail = clean[-3200:]
    omitted = len(clean) - len(head) - len(tail)
    return (
        f"{head}\n\n[...prompt compacted due to context size, {omitted} chars omitted...]\n\n{tail}"
    )


def _format_dt(value: datetime | None) -> str:
    if not value:
        return "No deadline"
    return value.strftime("%Y-%m-%d %H:%M")


def _extract_keywords(text: str) -> List[str]:
    words = re.findall(r"[a-zA-Z0-9_]{3,}", (text or "").lower())
    stop_words = {
        "with", "from", "that", "this", "have", "what", "about", "make", "using",
        "today", "tomorrow", "week", "tasks", "project", "projects", "please", "need",
        "plan", "schedule", "show", "help", "smart", "assistant", "more", "into",
    }
    unique = []
    seen = set()
    for word in words:
        if word in stop_words or word.isdigit():
            continue
        if word not in seen:
            unique.append(word)
            seen.add(word)
        if len(unique) >= 10:
            break
    return unique


def _normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _find_target_projects(
    project_catalog: List[Dict[str, Any]],
    user_prompt: str,
) -> List[Dict[str, Any]]:
    prompt_norm = _normalize_text(user_prompt)
    if not prompt_norm:
        return []

    focused: List[Dict[str, Any]] = []
    for project in project_catalog:
        name_norm = _normalize_text(project.get("name", ""))
        if not name_norm:
            continue
        if name_norm in prompt_norm or any(part in prompt_norm for part in name_norm.split() if len(part) > 4):
            focused.append(project)

    # Keep unique projects by id while preserving order.
    unique: List[Dict[str, Any]] = []
    seen = set()
    for item in focused:
        project_id = item.get("id")
        if project_id in seen:
            continue
        unique.append(item)
        seen.add(project_id)
    return unique[:4]


def _task_match_score(
    task: DbTask,
    project_name: str,
    keywords: List[str],
    focused_project_ids: set[int],
    now: datetime,
) -> int:
    score = 0
    haystack = _normalize_text(f"{task.title} {project_name}")

    for keyword in keywords:
        if keyword in haystack:
            score += 3

    if focused_project_ids and task.proj_id in focused_project_ids:
        score += 5

    if task.state in {"open", "todo", "doing"}:
        score += 1
    if task.is_urgent:
        score += 2
    if task.is_important:
        score += 1
    if task.deadline:
        hours_to_deadline = (task.deadline - now).total_seconds() / 3600
        if hours_to_deadline < 0:
            score += 4
        elif hours_to_deadline <= 24:
            score += 3
        elif hours_to_deadline <= 72:
            score += 2

    return score


def _build_smart_actions(
    now: datetime,
    focused_projects: List[Dict[str, Any]],
    urgent_tasks: List[Dict[str, Any]],
    upcoming_tasks: List[Dict[str, Any]],
    reminders: List[Dict[str, Any]],
    focus_score: int,
) -> List[str]:
    actions: List[str] = []

    overdue = []
    for task in upcoming_tasks:
        deadline = task.get("deadline")
        if deadline and datetime.fromisoformat(deadline) < now:
            overdue.append(task)

    if focused_projects:
        names = ", ".join(project["name"] for project in focused_projects[:2])
        actions.append(f"Prioritize a project-focused sprint for {names} before switching contexts.")
    if overdue:
        actions.append(
            "Resolve overdue items first: "
            + ", ".join(f"#{task['id']} {task['title'][:26]}" for task in overdue[:2])
            + "."
        )
    if urgent_tasks:
        actions.append(
            "Timebox urgent work now: "
            + ", ".join(f"#{task['id']}" for task in urgent_tasks[:3])
            + " in a 60-90 min focus block."
        )
    if reminders:
        actions.append(
            "Review near-term reminders before planning the next block to avoid context breaks."
        )
    if focus_score < 45:
        actions.append("Keep the plan narrow: choose only 3 must-win tasks for today.")
    elif focus_score >= 75:
        actions.append("You are in a high-output phase; protect deep-work blocks and avoid overloading.")

    return actions[:4]


def _serialize_task(task: DbTask, project_name: str | None = None) -> Dict[str, Any]:
    return {
        "id": task.id,
        "title": task.title,
        "state": task.state,
        "is_urgent": bool(task.is_urgent),
        "is_important": bool(task.is_important),
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "project": project_name,
    }


def get_or_create_memory(db: Session, user_id: int, mode: str) -> AssistantMemory:
    row = (
        db.query(AssistantMemory)
        .filter(AssistantMemory.owner == user_id, AssistantMemory.mode == mode)
        .first()
    )
    if row:
        return row

    row = AssistantMemory(owner=user_id, mode=mode, summary="", recent_history="[]")
    db.add(row)
    db.flush()
    return row


def build_planner_snapshot(
    db: Session,
    user_id: int,
    user_prompt: str,
    project_mode: str = "auto",
    focus_project_id: int | None = None,
    task_limit: int = 8,
) -> Dict[str, Any]:
    open_states = {"open", "todo", "doing"}
    mode = (project_mode or "auto").strip().lower()
    if mode not in {"auto", "strict", "cross"}:
        mode = "auto"

    now = datetime.utcnow()
    project_catalog_rows = (
        db.query(Project.id, Project.name)
        .filter(Project.owner == user_id)
        .order_by(Project.name.asc())
        .all()
    )
    project_catalog = [
        {"id": project_id, "name": project_name}
        for project_id, project_name in project_catalog_rows
    ]
    detected_focused_projects = _find_target_projects(project_catalog, user_prompt)
    scoped_project_ids: set[int] = set()
    if mode == "strict":
        if focus_project_id:
            scoped_project_ids = {focus_project_id}
        elif detected_focused_projects:
            scoped_project_ids = {p["id"] for p in detected_focused_projects[:1]}
    elif mode == "auto" and detected_focused_projects:
        scoped_project_ids = {p["id"] for p in detected_focused_projects}

    project_count = len(scoped_project_ids) if scoped_project_ids else len(project_catalog)
    tasks_base_query = db.query(DbTask).filter(DbTask.owner == user_id)
    if scoped_project_ids:
        tasks_base_query = tasks_base_query.filter(DbTask.proj_id.in_(scoped_project_ids))

    totals = {
        "projects": project_count,
        "tasks": tasks_base_query.with_entities(func.count(DbTask.id)).scalar() or 0,
        "done_tasks": tasks_base_query.filter(DbTask.state == "done").with_entities(func.count(DbTask.id)).scalar() or 0,
        "open_tasks": tasks_base_query.filter(DbTask.state.in_(open_states)).with_entities(func.count(DbTask.id)).scalar() or 0,
        "urgent_open_tasks": tasks_base_query.filter(
            DbTask.state.in_(open_states), DbTask.is_urgent.is_(True)
        ).with_entities(func.count(DbTask.id)).scalar() or 0,
        "doing_tasks": tasks_base_query.filter(DbTask.state == "doing").with_entities(func.count(DbTask.id)).scalar() or 0,
    }

    upcoming_reminders = (
        db.query(Reminder)
        .filter(Reminder.owner_id == user_id, Reminder.when >= now - timedelta(hours=1))
        .order_by(Reminder.when.asc())
        .limit(6)
        .all()
    )

    tasks_with_projects_query = (
        db.query(DbTask, Project.name)
        .join(Project, DbTask.proj_id == Project.id)
        .filter(DbTask.owner == user_id)
    )
    if scoped_project_ids:
        tasks_with_projects_query = tasks_with_projects_query.filter(DbTask.proj_id.in_(scoped_project_ids))

    urgent_rows = (
        tasks_with_projects_query
        .filter(DbTask.state.in_(open_states), DbTask.is_urgent.is_(True))
        .order_by(DbTask.deadline.is_(None), DbTask.deadline.asc(), DbTask.id.asc())
        .limit(task_limit)
        .all()
    )

    deadline_rows = (
        tasks_with_projects_query
        .filter(DbTask.state.in_(open_states), DbTask.deadline.isnot(None))
        .order_by(DbTask.deadline.asc(), DbTask.id.asc())
        .limit(task_limit)
        .all()
    )

    activity_rows = (
        db.query(Activity, DbTask.title)
        .join(DbTask, Activity.task_id == DbTask.id)
        .filter(DbTask.owner == user_id)
        .order_by(Activity.clock_in.desc())
        .limit(6)
        .all()
    )

    project_rows_query = (
        db.query(Project.id, Project.name, func.count(DbTask.id).label("task_count"))
        .outerjoin(
            DbTask,
            and_(
                DbTask.proj_id == Project.id,
                DbTask.owner == user_id,
                DbTask.state.in_(open_states),
            ),
        )
        .filter(Project.owner == user_id)
    )
    if scoped_project_ids:
        project_rows_query = project_rows_query.filter(Project.id.in_(scoped_project_ids))
    project_rows = (
        project_rows_query
        .group_by(Project.id, Project.name)
        .order_by(func.count(DbTask.id).desc(), Project.name.asc())
        .limit(7)
        .all()
    )
    focused_projects = detected_focused_projects
    if mode == "strict" and scoped_project_ids:
        focused_projects = [p for p in project_catalog if p["id"] in scoped_project_ids]
    focused_project_ids = scoped_project_ids or {item["id"] for item in focused_projects}

    candidate_rows = (
        tasks_with_projects_query
        .order_by(DbTask.deadline.is_(None), DbTask.deadline.asc(), DbTask.id.desc())
        .limit(180)
        .all()
    )

    keywords = _extract_keywords(user_prompt)
    scored_matches: List[tuple[int, Dict[str, Any]]] = []
    if keywords or focused_project_ids:
        for task, project_name in candidate_rows:
            score = _task_match_score(
                task=task,
                project_name=project_name or "",
                keywords=keywords,
                focused_project_ids=focused_project_ids,
                now=now,
            )
            if score <= 0:
                continue
            scored_matches.append((score, _serialize_task(task, project_name)))

    scored_matches.sort(
        key=lambda row: (
            -row[0],
            row[1]["deadline"] is None,
            row[1]["deadline"] or "",
            row[1]["id"],
        )
    )
    matched_entities = [entity for _, entity in scored_matches[:8]]

    urgent_tasks = [_serialize_task(task, project_name) for task, project_name in urgent_rows]
    upcoming_tasks = [_serialize_task(task, project_name) for task, project_name in deadline_rows]

    reminders = [
        {
            "id": reminder.id,
            "note": reminder.note,
            "when": reminder.when.isoformat(),
        }
        for reminder in upcoming_reminders
    ]

    recent_activity = [
        {
            "id": activity.id,
            "task_title": task_title,
            "status": activity.status,
            "clock_in": activity.clock_in.isoformat() if activity.clock_in else None,
            "clock_out": activity.clock_out.isoformat() if activity.clock_out else None,
            "description": (activity.description or "").strip()[:120],
        }
        for activity, task_title in activity_rows
    ]

    active_projects = [
        {
            "id": project_id,
            "name": project_name,
            "open_task_count": int(task_count or 0),
        }
        for project_id, project_name, task_count in project_rows
    ]

    focus_score = 0
    if totals["tasks"]:
        focus_score = round((totals["done_tasks"] / totals["tasks"]) * 100)
    smart_actions = _build_smart_actions(
        now=now,
        focused_projects=focused_projects,
        urgent_tasks=urgent_tasks,
        upcoming_tasks=upcoming_tasks,
        reminders=reminders,
        focus_score=focus_score,
    )

    sections: List[str] = [
        "Planner snapshot:",
        (
            f"- Totals: {totals['projects']} projects, {totals['tasks']} tasks "
            f"({totals['done_tasks']} done, {totals['open_tasks']} open, {totals['urgent_open_tasks']} urgent open)."
        ),
        f"- Focus score: {focus_score}%.",
    ]
    if focused_projects:
        sections.append(
            f"- Project mode: {mode}. Project focus detected in prompt: "
            + "; ".join(project["name"] for project in focused_projects)
            + "."
        )

    if active_projects:
        sections.append(
            "- Active projects: "
            + "; ".join(
                f"{project['name']} ({project['open_task_count']} open)" for project in active_projects[:5]
            )
            + "."
        )

    if matched_entities:
        sections.append(
            "- Prompt-matched tasks: "
            + "; ".join(
                f"#{item['id']} {item['title'][:48]}" for item in matched_entities[:5]
            )
            + "."
        )

    if urgent_tasks:
        sections.append(
            "- Urgent tasks: "
            + "; ".join(
                f"#{item['id']} {item['title'][:45]} (due {_format_dt(datetime.fromisoformat(item['deadline'])) if item['deadline'] else 'No deadline'})"
                for item in urgent_tasks[:5]
            )
            + "."
        )

    if reminders:
        sections.append(
            "- Upcoming reminders: "
            + "; ".join(
                f"{item['note'][:40]} at {_format_dt(datetime.fromisoformat(item['when']))}"
                for item in reminders[:4]
            )
            + "."
        )

    if recent_activity:
        sections.append(
            "- Recent activity: "
            + "; ".join(
                f"{item['task_title'][:36]} ({item['status']})"
                for item in recent_activity[:4]
            )
            + "."
        )
    if smart_actions:
        sections.append(
            "- Suggested execution strategy: "
            + " | ".join(smart_actions[:3])
        )

    context_block = "\n".join(sections)

    return {
        "metrics": {
            **totals,
            "focus_score": focus_score,
            "upcoming_reminders": len(reminders),
        },
        "project_mode": mode,
        "scope_project_ids": sorted(list(scoped_project_ids)),
        "active_projects": active_projects,
        "focused_projects": focused_projects,
        "urgent_tasks": urgent_tasks,
        "upcoming_tasks": upcoming_tasks,
        "matched_entities": matched_entities,
        "upcoming_reminders": reminders,
        "recent_activity": recent_activity,
        "keywords": keywords,
        "smart_actions": smart_actions,
        "context_block": context_block,
        "matched_entities_count": len(matched_entities),
    }


def build_compact_context(
    db: Session,
    user_id: int,
    mode: str,
    user_prompt: str,
    incoming_history: List[Dict[str, str]] | None = None,
    project_mode: str = "auto",
    focus_project_id: int | None = None,
) -> Dict[str, Any]:
    memory = get_or_create_memory(db, user_id, mode)
    stored_history = _safe_json_loads(memory.recent_history or "[]", [])
    incoming_history = incoming_history or []

    merged: List[Dict[str, str]] = (stored_history + incoming_history)[-MAX_HISTORY_ITEMS:]
    compact_prompt = _compact_prompt(user_prompt)
    planner_snapshot = build_planner_snapshot(
        db=db,
        user_id=user_id,
        user_prompt=user_prompt,
        project_mode=project_mode,
        focus_project_id=focus_project_id,
    )

    conversation_blob = _summarize_turns(merged, max_chars=3200)
    summary_blob = (memory.summary or "").strip()

    context = (
        f"Long-term memory summary:\n{summary_blob or 'No long-term memory yet.'}\n\n"
        f"Recent conversation (compact):\n{conversation_blob or 'No recent turns.'}\n\n"
        f"{planner_snapshot['context_block']}\n\n"
        "Instruction: Ground every recommendation in the planner snapshot. "
        "When possible, cite task IDs and project names explicitly. "
        "Structure the answer as: Situation, Priorities, Next 3 actions, and Timeboxing.\n\n"
        f"Current user request:\n{compact_prompt}"
    )

    if len(context) > MAX_CONTEXT_CHARS:
        # Reduce aggressively while preserving latest request and highest-value planner info.
        short_conversation = _summarize_turns(merged[-6:], max_chars=1300)
        short_summary = summary_blob[:900]
        compact_snapshot = planner_snapshot["context_block"][:2600]
        context = (
            f"Memory summary:\n{short_summary or 'No memory summary.'}\n\n"
            f"Recent conversation:\n{short_conversation or 'No recent turns.'}\n\n"
            f"Planner snapshot:\n{compact_snapshot}\n\n"
            f"Current request:\n{compact_prompt}"
        )

    estimated_tokens = _estimate_tokens(context)
    return {
        "context_text": context,
        "memory_row": memory,
        "merged_history": merged,
        "estimated_tokens": estimated_tokens,
        "compacted": len(context) >= COMPACT_TARGET_CHARS,
        "planner_snapshot": planner_snapshot,
    }


def update_memory_after_response(
    db: Session,
    memory: AssistantMemory,
    merged_history: List[Dict[str, str]],
    user_prompt: str,
    assistant_response: str,
) -> None:
    updated_history = (
        merged_history
        + [{"role": "user", "content": user_prompt}]
        + [{"role": "assistant", "content": assistant_response}]
    )[-MAX_HISTORY_ITEMS:]

    previous_summary = (memory.summary or "").strip()
    recent_summary = _summarize_turns(updated_history[-8:], max_chars=1400)
    memory.summary = (
        f"{previous_summary}\n{recent_summary}".strip()[-2600:]
        if previous_summary
        else recent_summary
    )
    memory.recent_history = json.dumps(updated_history, ensure_ascii=True)
    memory.updated_at = datetime.utcnow()
    db.add(memory)
    db.commit()
