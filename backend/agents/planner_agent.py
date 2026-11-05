"""Deterministic planning helpers with explicit approval gates."""
from __future__ import annotations
from datetime import date, datetime

_PRIORITY = {"high": 0, "medium": 1, "low": 2}

def _deadline_key(task: dict) -> datetime:
    value = task.get("deadline") or task.get("due_date")
    if not value: return datetime.max
    try: return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError: return datetime.max

def rank_tasks(tasks: list[dict]) -> list[dict]:
    return sorted(tasks, key=lambda t: (_deadline_key(t), _PRIORITY.get(str(t.get("priority", "low")).lower(), 2), t.get("estimated_effort", 999)))

def detect_conflicts(tasks: list[dict]) -> list[dict]:
    grouped = {}
    for task in tasks:
        key = str(task.get("deadline") or task.get("due_date") or "").strip()
        if key: grouped.setdefault(key, []).append(task)
    return [{"deadline": key, "tasks": items} for key, items in grouped.items() if len(items) > 1]

def create_daily_plan(tasks: list[dict], approved: bool = False) -> dict:
    ranked = rank_tasks(tasks)
    result = {"top_priorities": ranked[:3], "conflicts": detect_conflicts(tasks), "requires_confirmation": not approved, "saved": bool(approved)}
    result["response"] = "Action: daily plan approved and saved." if approved else "Proposed a daily plan with up to three priorities. Reply ‘confirm’ to save it."
    return result

def create_study_plan(exam_date: str, available_hours: float, subject: str = "study", approved: bool = False) -> dict:
    exam = date.fromisoformat(exam_date)
    days = max((exam - date.today()).days, 1)
    result = {"subject": subject, "exam_date": exam_date, "days": days, "daily_hours": round(float(available_hours) / days, 2), "requires_confirmation": not approved, "saved": bool(approved)}
    result["response"] = "Action: study plan approved and saved." if approved else f"Proposed a study plan for {subject}. Reply ‘confirm’ to save it."
    return result
