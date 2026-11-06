"""Planner service: ranking, conflict detection, daily and study plans.

Ranking rule (in order): nearest deadline, then highest priority, then least
effort — so the cheapest urgent thing surfaces first.
"""

from __future__ import annotations

import json
from datetime import date, datetime

from ..database import connect
from .task_service import list_tasks, suggest_postponements

MAX_PRIORITIES = 3


def rank_tasks(tasks: list[dict] | None = None) -> list[dict]:
    """Sort by deadline, then priority, then estimated effort."""
    items = list_tasks() if tasks is None else tasks
    return sorted(
        items,
        key=lambda t: (
            t.get("deadline") or "9999-12-31",
            t.get("priority", 3),
            t.get("estimated_minutes", 30),
        ),
    )


def detect_conflicts(tasks: list[dict] | None = None) -> list[dict]:
    """Group tasks that share a deadline — the classic overbooked day."""
    items = list_tasks() if tasks is None else tasks
    grouped: dict[str, list[dict]] = {}
    for task in items:
        if task.get("status") not in (None, "pending"):
            continue
        key = (task.get("deadline") or "").strip()
        if key:
            grouped.setdefault(key, []).append(task)
    return [
        {
            "deadline": day,
            "count": len(members),
            "tasks": [m["title"] for m in members],
            "minutes": sum(m.get("estimated_minutes") or 0 for m in members),
        }
        for day, members in sorted(grouped.items())
        if len(members) > 1
    ]


def study_plan(exam_date: str, study_hours: float, subject: str | None = None) -> dict:
    """Split available study time across the days remaining before an exam."""
    try:
        exam = datetime.fromisoformat(exam_date).date()
    except (ValueError, TypeError):
        return {"error": "exam_date must look like YYYY-MM-DD"}

    days_left = (exam - date.today()).days
    if days_left < 0:
        return {"error": "That exam date is already in the past."}

    days_left = max(days_left, 1)
    hours = max(float(study_hours or 0), 0.0)
    return {
        "subject": subject or "your subject",
        "exam_date": exam_date,
        "days_left": days_left,
        "total_hours": round(hours, 2),
        "hours_per_day": round(hours / days_left, 2),
        "advice": (
            "Start today — the daily load is small."
            if hours / days_left <= 1.5
            else "That is a heavy daily load. Consider freeing time or splitting the subject."
        ),
    }


def build(request: dict | None = None) -> dict:
    """Assemble the plan payload shared by the API, agents, and CLI demo."""
    request = request or {}
    open_tasks = [t for t in list_tasks() if t["status"] == "pending"]
    ranked = rank_tasks(open_tasks)
    top = ranked[:MAX_PRIORITIES]
    conflicts = detect_conflicts(open_tasks)

    result: dict = {
        "top_priorities": top,
        "conflicts": conflicts,
        "total_open": len(open_tasks),
        "focus_minutes": sum(t.get("estimated_minutes") or 0 for t in top),
        "suggested_postponements": suggest_postponements(2) if len(conflicts) else [],
    }

    if request.get("exam_date"):
        result["study_plan"] = study_plan(
            request["exam_date"],
            request.get("study_hours") or 0,
            request.get("study_subject"),
        )
    return result


def save(request: dict | None = None, approved: bool = False) -> dict:
    """Persist a plan only after approval; always return the payload."""
    request = request or {}
    payload = build(request)
    plan_id = None
    if approved:
        with connect() as con:
            cursor = con.execute(
                "INSERT INTO daily_plans (plan_date, content, approved) VALUES (?,?,1)",
                (request.get("plan_date") or str(date.today()), json.dumps(payload)),
            )
            plan_id = cursor.lastrowid
    return {
        "content": payload,
        "plan_id": plan_id,
        "approved": approved,
        "needs_approval": not approved,
    }


def create_daily_plan(plan_date: str | None = None, approved: bool = False) -> dict:
    return save({"plan_date": plan_date}, approved=approved)


def create_study_plan(request: dict, approved: bool = False) -> dict:
    return save(request, approved=approved)


# Compatibility alias kept for existing imports.
create_plan = save
