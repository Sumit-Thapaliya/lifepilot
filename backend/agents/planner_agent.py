"""Planner Agent.

Role: prioritise tasks, detect conflicting deadlines, build a daily plan of at
most three priorities, build study plans, and suggest what to postpone.

Contract: it always shows the proposed plan first and asks for approval. It
never saves a plan or changes a task on its own.
"""

from __future__ import annotations

from ..models import Proposal
from ..services import planner_service, task_service

NAME = "Planner"
MAX_PRIORITIES = 3


def propose_day() -> Proposal:
    """Build a daily plan proposal from the current open tasks."""
    plan = planner_service.build({})
    top = plan["top_priorities"]
    conflicts = plan["conflicts"]
    suggested = plan["suggested_postponements"]

    if not top:
        return Proposal(
            kind="plan",
            summary="no open tasks — nothing to plan yet",
            payload=plan,
            requires_confirmation=False,
        )

    lines = ["Planner — here is my proposed plan for today (max 3 priorities):"]
    lines.extend(
        f"  {i}. {t['title']} — priority {t['priority']}, due {t['deadline'] or 'no date'}, "
        f"~{t['estimated_minutes']} min"
        for i, t in enumerate(top, 1)
    )
    lines.append(f"Total focus time: {plan['focus_minutes']} minutes.")

    if conflicts:
        lines.append("Deadline conflicts I found:")
        lines.extend(
            f"  ! {c['deadline']}: {c['count']} tasks ({', '.join(c['tasks'])})"
            for c in conflicts
        )
        if suggested:
            lines.append("Suggested to postpone:")
            lines.extend(f"  - {t['title']} (priority {t['priority']})" for t in suggested)

    lines.append("Save this plan? Reply 'yes' to save or 'no' to keep it as a draft.")

    return Proposal(
        kind="plan",
        summary=f"{len(top)} priorities, {plan['focus_minutes']} min, {len(conflicts)} conflict(s)",
        payload=plan,
        requires_confirmation=True,
    )


def respond(proposal: Proposal) -> str:
    """Render the proposal as a short chat message built from its payload."""
    plan = proposal.payload
    top = plan.get("top_priorities") or []
    if not top:
        return "Planner — no open tasks yet. Say 'add a task …' and I'll plan around it."

    lines = ["Planner — proposed plan for today:"]
    lines.extend(
        f"  {i}. {t['title']} — priority {t['priority']}, due {t['deadline'] or 'no date'}"
        for i, t in enumerate(top, 1)
    )
    lines.append(f"Focus time: {plan.get('focus_minutes', 0)} min.")

    if plan.get("conflicts"):
        lines.append("Conflicts:")
        lines.extend(
            f"  ! {c['deadline']}: {c['count']} tasks" for c in plan["conflicts"]
        )
        for t in plan.get("suggested_postponements") or []:
            lines.append(f"  Suggested to postpone: {t['title']}")

    lines.append("Nothing saved yet. Reply 'yes' to save this plan or 'no' to discard.")
    return "\n".join(lines)


def propose_study_plan(exam_date: str, study_hours: float, subject: str | None = None) -> Proposal:
    """Propose a study plan split across the days before an exam."""
    plan = planner_service.study_plan(exam_date, study_hours, subject)
    if plan.get("error"):
        return Proposal(kind="study_plan", summary=plan["error"], payload=plan,
                        requires_confirmation=False)

    summary = (
        f"{plan['days_left']} days left for {plan['subject']}; "
        f"{plan['hours_per_day']} h/day from {plan['total_hours']} h total"
    )
    return Proposal(kind="study_plan", summary=summary, payload=plan, requires_confirmation=True)


def respond_study(proposal: Proposal) -> str:
    plan = proposal.payload
    if plan.get("error"):
        return f"Planner — {plan['error']}"
    return (
        f"Planner — study plan for {plan['subject']}:\n"
        f"  Exam: {plan['exam_date']} ({plan['days_left']} days left)\n"
        f"  Total time: {plan['total_hours']} h → {plan['hours_per_day']} h/day\n"
        f"  {plan['advice']}\n"
        "Nothing saved yet. Reply 'yes' to save this plan or 'no' to discard."
    )


def save(proposal: Proposal, approved: bool = True) -> dict:
    """Persist the plan only on approval."""
    if not approved:
        return {"agent": NAME, "saved": None, "reply": "Plan discarded. Nothing was saved."}

    if proposal.kind == "study_plan":
        result = planner_service.save(proposal.payload, approved=True)
        return {
            "agent": NAME,
            "saved": result,
            "reply": f"Saved study plan #{result['plan_id']} for {proposal.payload.get('subject', 'your subject')}.",
        }

    result = planner_service.save({}, approved=True)
    return {"agent": NAME, "saved": result, "reply": f"Saved today's plan #{result['plan_id']}."}


def handle(message: str, context: str = "day") -> dict:
    """One-turn handler: propose a plan (or a study plan) without saving."""
    if "exam" in message.lower() and context == "study":
        proposal = propose_study_plan(
            exam_date=_extract_date(message) or "2099-01-01",
            study_hours=_extract_hours(message) or 10,
        )
        return {
            "agent": NAME,
            "requires_confirmation": proposal.requires_confirmation,
            "pending": proposal,
            "reply": respond_study(proposal),
        }

    proposal = propose_day()
    return {
        "agent": NAME,
        "requires_confirmation": proposal.requires_confirmation,
        "pending": proposal,
        "reply": respond(proposal),
    }


def suggest_postponements(limit: int = 2) -> list[dict]:
    """Expose the service helper so the chat layer can show the suggestion."""
    return task_service.suggest_postponements(limit)


# ---------------------------------------------------------------------------
# Small extraction helpers used by the study-plan branch
# ---------------------------------------------------------------------------

import re

_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", re.I)


def _extract_date(message: str) -> str | None:
    match = _DATE.search(message)
    return match.group(1) if match else None


def _extract_hours(message: str) -> float | None:
    match = _HOURS.search(message)
    return float(match.group(1)) if match else None
