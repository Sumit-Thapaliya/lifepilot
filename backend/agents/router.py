"""Intent router: decides which agent should answer.

This is deliberately a readable keyword/heuristic router rather than an LLM
call, so the project runs with no paid API and behaves identically every time.

Specific product intents are checked first. General questions, greetings and
status updates go to the Assistant; only actionable/task-like text goes to
Capture. Every agent still owns its own logic and approval step.
"""

from __future__ import annotations

import re
from typing import Optional

from ..models import Proposal
from . import capture_agent, general_agent, planner_agent, reminder_agent

# Intent triggers, checked in order. More specific intents come first.
PLAN_TRIGGERS = ("plan my day", "plan today", "daily plan", "what should i do", "prioritise", "prioritize")
STUDY_TRIGGERS = ("study plan", "exam", "revise for")
MORNING_TRIGGERS = ("morning briefing", "good morning", "morning")
EVENING_TRIGGERS = ("wrap up", "evening review", "end of day", "how did today go")
BILL_TRIGGERS = ("bill reminder", "bills due", "what bills", "due date")
POSTPONE_TRIGGERS = ("postpone", "push back", "move to tomorrow")
DELETE_TRIGGERS = ("delete task", "remove task", "cancel task")

QUESTION_STARTERS = (
    "what", "what's", "who", "who's", "why", "why's", "how", "how's",
    "when", "when's", "where", "where's", "which", "can you", "could you",
    "would you", "do you", "does ", "is ", "are ", "am ", "tell me",
    "explain", "help", "show me", "i have a question", "i wonder",
    "any idea", "do i", "should i",
)

STATUS_UPDATE_TRIGGERS = (
    "still working", "in progress", "almost done", "not yet", "blocked",
    "halfway", "working on", "finished ", "done with", "completed ",
    "made progress", "no progress", "on track",
)

TASK_MARKERS = (
    "add a task", "new task", "create task", "make a task", "track a bill",
    "todo", "to-do", "task:", "bill:", "i need to", "i have to", "need to",
    "have to", "remind me", "remember to", "don't forget", "dont forget",
    "urgent", "priority", "deadline", "estimated", "due date",
)

ACTION_VERBS = {
    "finish", "submit", "pay", "call", "buy", "write", "prepare", "review",
    "clean", "book", "send", "read", "study", "revise", "practice", "walk",
    "check", "fix", "complete", "organize", "organise", "pick", "drop",
    "water", "email", "order", "renew", "register", "apply", "attend",
    "meet", "cook", "wash", "update", "draft", "print", "file", "visit",
    "message", "text", "reply", "confirm", "schedule", "plan", "add",
}

# A direct request can be phrased as a question ("can you add a task to …?")
# and must still reach Capture rather than the general answer path.
DIRECT_TASK_RE = re.compile(
    r"(?:"
    r"\b(?:add|create|make|log|track|remember)\s+(?:a\s+)?(?:task|bill|reminder)\b"
    r"(?:\s+(?:to|for|about|:)\s+\S+|\s*[-:—]\s*\S+)"
    r"|\bremind me to\s+\S+"
    r"|\bremember to\s+\S+"
    r"|\bi\s+(?:need|have)\s+to\s+\S+"
    r"|\bdon'?t forget to\s+\S+"
    r"|\bput\s+.+?\s+on my\s+(?:list|tasks)\b"
    r")",
    re.I,
)

DEADLINE_RE = re.compile(
    r"\b(?:by|before|due|on)\s+"
    r"(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|next\s+\w+|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?)\b",
    re.I,
)


def _is_general_question(lowered: str) -> bool:
    return lowered.endswith("?") or any(lowered.startswith(s) for s in QUESTION_STARTERS)


def _looks_like_task(lowered: str) -> bool:
    """True only for actionable text, not for every sentence a user types."""
    if any(marker in lowered for marker in TASK_MARKERS):
        return True
    if DEADLINE_RE.search(lowered):
        return True
    words = re.sub(r"^(?:please|kindly|hey|ok|okay)\s+", "", lowered).split()
    return bool(words and words[0] in ACTION_VERBS)


def detect(message: str) -> str:
    """Return one of: planner, planner_study, reminder_morning,
    reminder_evening, reminder_bills, reminder_postpone, reminder_delete,
    general, capture."""
    lowered = message.lower().strip()

    if not lowered:
        return "general"
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

    # A direct request wins even when phrased as "can you …?".
    if DIRECT_TASK_RE.search(lowered):
        return "capture"
    # Progress replies are conversation, not new tasks.
    if any(trigger in lowered for trigger in STATUS_UPDATE_TRIGGERS):
        return "general"
    # Any other question/greeting gets a real answer, never a task proposal.
    if _is_general_question(lowered):
        return "general"
    if _looks_like_task(lowered):
        return "capture"
    return "general"


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
    if intent == "general":
        return general_agent.answer(message)

    return capture_agent.handle(message)


NEGATIVE_WORDS = {"no", "n", "nope", "cancel", "discard", "don't", "dont", "stop"}


def _is_no(message: str) -> bool:
    return message.strip().lower().rstrip(".!") in NEGATIVE_WORDS


def _is_yes(message: str) -> bool:
    """A tiny local affirmative check so the router needs no agent import."""
    return message.strip().lower().rstrip(".!") in {
        "yes", "y", "yeah", "yep", "save", "save it", "confirm", "ok", "okay", "sure", "do it",
    }
