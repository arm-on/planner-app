from datetime import datetime
from typing import Any, Dict, List, Optional

from core.crewai_env import disable_crewai_telemetry

disable_crewai_telemetry()

from crewai import Agent, Crew, LLM, Process, Task
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.assistant_context import build_compact_context, build_planner_snapshot, update_memory_after_response
from core.database import get_db
from models.keys import Key
from models.models import Model
from models.user import User

router = APIRouter()


class AgenticQuery(BaseModel):
    model_api_key: str
    user_prompt: str
    conversation_history: Optional[List[Dict[str, str]]] = []
    project_mode: str = "auto"
    focus_project_id: Optional[int] = None


class AgenticResponse(BaseModel):
    response: str
    agent_used: str
    tools_used: List[str]
    reasoning: str
    meta: Optional[Dict[str, Any]] = None


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


def choose_agent(user_prompt: str) -> tuple[str, str]:
    prompt = user_prompt.lower()
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


def build_user_context(
    current_user: User,
    db: Session,
    user_prompt: str,
    project_mode: str,
    focus_project_id: Optional[int],
) -> Dict[str, Any]:
    snapshot = build_planner_snapshot(
        db=db,
        user_id=current_user.id,
        user_prompt=user_prompt,
        project_mode=project_mode,
        focus_project_id=focus_project_id,
    )
    return {
        "metrics": snapshot["metrics"],
        "active_projects": snapshot["active_projects"][:5],
        "focused_projects": snapshot["focused_projects"][:4],
        "urgent_tasks": snapshot["urgent_tasks"][:6],
        "upcoming_tasks": snapshot["upcoming_tasks"][:6],
        "upcoming_reminders": snapshot["upcoming_reminders"][:5],
        "recent_activity": snapshot["recent_activity"][:5],
        "smart_actions": snapshot["smart_actions"][:3],
        "matched_entities_count": snapshot["matched_entities_count"],
        "keywords": snapshot["keywords"],
        "timezone": current_user.timezone,
        "project_mode": snapshot.get("project_mode", "auto"),
    }


def run_agentic_crewai(
    user_prompt: str,
    model: Model,
    context: Dict[str, Any],
    agent_name: str,
    agent_goal: str,
) -> str:
    llm = LLM(
        model=model.name,
        base_url=model.base_url,
        api_key=model.api_key,
        temperature=0.2,
    )

    specialist = Agent(
        role=agent_name,
        goal=agent_goal,
        backstory=(
            "You are a specialist in personal planning software. "
            "You answer with concise, actionable markdown."
        ),
        allow_delegation=False,
        llm=llm,
        verbose=False,
    )

    task = Task(
        description=(
            "{user_prompt}\n\n"
            "Known user context (JSON-like):\n{user_context}\n\n"
            "Respond with practical next actions and clear prioritization. "
            "Tie recommendations to project names and task IDs when available."
        ),
        expected_output=(
            "Markdown with sections: Situation, Priorities, Next 3 actions, and Timeboxing."
        ),
        agent=specialist,
    )

    crew = Crew(
        agents=[specialist],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff(
        inputs={
            "user_prompt": user_prompt,
            "user_context": str(context),
        }
    )
    return getattr(result, "raw", str(result))


@router.post("/agentic-query", response_model=AgenticResponse)
async def agentic_query(
    query: AgenticQuery,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model = db.query(Model).filter(
        Model.api_key == query.model_api_key,
        Model.owner == current_user.id,
    ).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    agent_name, agent_goal = choose_agent(query.user_prompt)
    context = build_user_context(
        current_user=current_user,
        db=db,
        user_prompt=query.user_prompt,
        project_mode=query.project_mode,
        focus_project_id=query.focus_project_id,
    )

    try:
        compact = build_compact_context(
            db=db,
            user_id=current_user.id,
            mode="agentic",
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

        response_text = run_agentic_crewai(
            user_prompt=effective_prompt,
            model=model,
            context=context,
            agent_name=agent_name,
            agent_goal=agent_goal,
        )
        update_memory_after_response(
            db=db,
            memory=compact["memory_row"],
            merged_history=compact["merged_history"],
            user_prompt=query.user_prompt,
            assistant_response=response_text,
        )

        return AgenticResponse(
            response=response_text,
            agent_used=agent_name,
            tools_used=[
                "task_summary",
                "project_summary",
                "activity_summary",
                "reminder_summary",
            ],
            reasoning=f"Selected {agent_name} based on prompt intent classification.",
            meta={
                "estimated_tokens": compact["estimated_tokens"],
                "compacted": compact["compacted"],
                "matched_entities": context.get("matched_entities_count", 0),
                "focused_projects": len(context.get("focused_projects", [])),
                "project_mode": context.get("project_mode", "auto"),
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CrewAI error: {str(exc)}")
