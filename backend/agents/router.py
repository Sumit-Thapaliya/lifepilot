"""Intent router: decides which of the three agents should answer.

This is deliberately a simple, readable keyword router rather than an LLM call,
so the project runs with no paid API and behaves identically every time. Each
agent still owns its own logic and its own approval step.
"""

from __future__ import annotations

from typing import Optional

from ..models import Proposal
from . import capture_agent, planner_agent, reminder_agent

# Intent triggers, checked in order. More specific intents come first.
PLAN_TRIGGERS = ("plan my day", "plan today", "daily plan", "what should i do", "prioritise", "prioritize")
STUDY_TRIGGERS = ("study plan", "exam", "revise for")
MORNING_TRIGGERS = ("morning briefing", "good morning", "morning")
EVENING_TRIGGERS = ("wrap up", "evening review", "end of day", "how did today go")
BILL_TRIGGERS = ("bill reminder", "bills due", "what bills", "due date")
POSTPONE_TRIGGERS = ("postpone", "push back", "move to tomorrow")
DELETE_TRIGGERS = ("delete task", "remove task", "cancel task")


def detect(message: str) -> str:
    """Return one of: planner, planner_study, reminder_morning,
    reminder_evening, reminder_bills, reminder_postpone, reminder_delete,
    capture."""
    lowered = message.lower().strip()

    if any(trigger in lowered for trigger in STUDY_TRIGGERS) and "exam" in lowered:
        return "planner_study"
    if any(trigger in lowered for trigger in PLAN_TRIGGERS):
        return "planner"
    if any(trigger in lowered for trigger in EVENING_TRIGGERS):
        return "reminder_evening"
    if any(trigger in lowered for trigger in MORNING_TRIGGERS):
        return "reminder_morning"
    if any(trigger in lowered for trigger in BILL_TRIGGERS):
        return "reminder_bills"
    if any(trigger in lowered for trigger in DELETE_TRIGGERS):
        return "reminder_delete"
    if any(trigger in lowered for trigger in POSTPONE_TRIGGERS):
        return "reminder_postpone"
    return "capture"


def route(
    message: str,
    pending: Optional[Proposal] = None,
    photo_result: Optional[dict] = None,
) -> dict:
    """Send one message to the right agent and return its chat response.

    ``pending`` is a proposal still awaiting a yes/no. If present, the message
    is treated as the answer to that proposal rather than a new intent.

    ``photo_result`` lets the Capture agent handle an OCR result from the chat
    layer, so photos flow through the same propose-then-confirm contract.
    """
    if photo_result is not None:
        return capture_agent.handle_photo(photo_result)

    if pending is not None:
        if pending.kind in ("task", "photo"):
            return capture_agent.handle(message, pending=pending)
        if pending.kind in ("plan", "study_plan"):
            if _is_yes(message):
                return planner_agent.save(pending, approved=True)
            if _is_no(message):
                return planner_agent.save(pending, approved=False)
            # Neither yes nor no: never discard silently. Ask again.
            return {
                "agent": planner_agent.NAME,
                "requires_confirmation": True,
                "pending": pending,
                "reply": (
                    "I still have an unsaved plan waiting. Reply 'yes' to save it "
                    "or 'no' to discard before we move on."
                ),
            }

    intent = detect(message)

    if intent == "planner":
        return planner_agent.handle(message)
    if intent == "planner_study":
        return planner_agent.handle(message, context="study")
    if intent == "reminder_morning":
        result = reminder_agent.morning()
        return {"agent": reminder_agent.NAME, "reply": result["message"]}
    if intent == "reminder_evening":
        result = reminder_agent.evening()
        return {"agent": reminder_agent.NAME, "reply": result["message"]}
    if intent == "reminder_bills":
        result = reminder_agent.bills()
        return {"agent": reminder_agent.NAME, "reply": result["message"]}
    if intent in ("reminder_postpone", "reminder_delete"):
        return {
            "agent": reminder_agent.NAME,
            "reply": (
                "Tell me the task number and I'll ask you to confirm first. "
                "For example: 'postpone 3 to tomorrow'."
            ),
        }

    return capture_agent.handle(message)


NEGATIVE_WORDS = {"no", "n", "nope", "cancel", "discard", "don't", "dont", "stop"}


def _is_no(message: str) -> bool:
    return message.strip().lower().rstrip(".!") in NEGATIVE_WORDS


def _is_yes(message: str) -> bool:
    """A tiny local affirmative check so the router needs no agent import."""
    return message.strip().lower().rstrip(".!") in {
        "yes", "y", "yeah", "yep", "save", "save it", "confirm", "ok", "okay", "sure", "do it",
    }
