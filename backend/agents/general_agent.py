"""General Assistant — answers questions that are not actionable tasks.

Capture turns plain language into a proposal. It should not turn greetings,
help requests, project questions, or progress updates into a fake task. This
module gives those messages a real answer instead.

Rules mode works offline and handles common LifePilot questions. If a language
model is configured, unknown general questions can be answered by it. Either
way this module only returns text: it never writes to SQLite.
"""

from __future__ import annotations

from ..services import llm_service, scheduler_service

NAME = "Assistant"

GREETINGS = {
    "hi", "hello", "hey", "hi there", "hello there", "good morning",
    "good afternoon", "good evening", "thanks", "thank you", "namaste",
}

NO_PENDING = {
    "yes", "y", "yeah", "yep", "ok", "okay", "sure", "no", "n", "nope",
    "cancel", "discard", "stop", "thanks", "thank you",
}

CAPABILITIES = (
    "I can read plain-language tasks, show and edit the fields I understood, "
    "propose a top-three daily plan, track bills, send morning/evening briefings, "
    "check in on open tasks, and answer questions about LifePilot. I only ask to "
    "save something when your message looks like an actionable task."
)

ABOUT = (
    "LifePilot is a local-first life organizer with three thin agents: Capture "
    "reads a sentence, Planner ranks a small daily plan, and Reminder sends "
    "briefings and nudges. Everything is approved by you before it is stored in "
    "a local SQLite database."
)

APPROVAL = (
    "Nothing is written until you say yes. A proposal is held in memory for your "
    "conversation, not inserted as a row. The API and service layers also require "
    "approved=true, so a prompt cannot accidentally save, delete, or postpone data."
)

PRIVACY = (
    "Your data stays in backend/data/lifepilot.db on this machine. .env, *.db, and "
    "outbox.log are gitignored. With no model provider or webhook configured, no "
    "application data leaves the machine."
)

HOW_TO_ADD = (
    "Write an actionable sentence, for example: 'add a task to submit the lab "
    "report by Friday' or simply 'Submit lab report by Friday'. I will show the "
    "title, category, priority, date, and effort, then ask yes or no. General "
    "questions are answered without creating a proposal."
)

OFFLINE = (
    "I do not fetch live weather, news, or other internet data. LifePilot runs "
    "offline with deterministic rules by default; an optional model only improves "
    "how sentences are understood."
)

STATUS_UPDATE = (
    "Thanks for the update — I have not changed any task. Use the dashboard "
    "checkbox or its task controls when something is done; a status message "
    "never edits your data."
)

DEFAULT = (
    "I can answer questions about LifePilot and help with tasks, plans, bills, "
    "and reminders. I only propose saving something when your message looks "
    "like an actionable task. Try 'what can you do?' or 'add a task to buy milk'."
)

STATUS_WORDS = (
    "still working", "in progress", "almost done", "not yet", "blocked",
    "halfway", "working on", "finished ", "done with", "completed ",
    "made progress", "no progress", "on track",
)

REMINDER_WORDS = (
    "progress check", "check in", "check-in", "remind me", "reminder",
    "briefing", "time to time", "nudge",
)

SYSTEM = (
    "You are LifePilot's concise local assistant. Answer the user's general "
    "question in two or three sentences. Be accurate about LifePilot: it is "
    "local-first, approval-first, and only task-like messages create proposals. "
    "Do not claim to have saved, changed, deleted, or fetched anything. "
    "Do not ask to add a task unless the user's message itself is a task. "
    "Plain text only, no markdown."
)


def _known_answer(message: str) -> str | None:
    """Fast, deterministic answers. Return None for an open-ended question."""
    lowered = message.strip().lower().rstrip(".!?")

    if lowered in GREETINGS:
        return "Hi! I can answer questions about LifePilot or help you organise tasks, plans, bills, and reminders."
    if lowered in NO_PENDING:
        return "There is no pending proposal to confirm right now. Ask me a question or tell me a task in plain language."
    if any(word in lowered for word in STATUS_WORDS):
        return STATUS_UPDATE
    if "what can you do" in lowered or "what do you do" in lowered or lowered in {"help", "commands", "options"}:
        return CAPABILITIES
    if "what is lifepilot" in lowered or "about lifepilot" in lowered or "who are you" in lowered:
        return ABOUT
    if "approval" in lowered or "nothing is saved" in lowered or "proposal" in lowered:
        return APPROVAL
    if "privacy" in lowered or "where is my data" in lowered or "local sqlite" in lowered:
        return PRIVACY
    if any(word in lowered for word in REMINDER_WORDS):
        hours = scheduler_service.progress_interval_hours()
        cadence = f"every {hours} hours" if hours else "disabled by configuration"
        return (
            "Yes. The scheduler sends morning/evening briefings, bill and due-date "
            f"nudges, and a deduplicated progress check for one open task {cadence} "
            "during your active hours. It only reads tasks; it never changes them."
        )
    if "how do i add" in lowered or "how to add" in lowered or "how does" in lowered and "work" in lowered:
        return HOW_TO_ADD
    if any(word in lowered for word in ("weather", "news", "stock", "internet", "online search")):
        return OFFLINE
    if "how are you" in lowered:
        return "I'm running locally and ready. I can answer questions, propose tasks, or build a plan."
    return None


def answer(message: str) -> dict:
    """Return a chat response without creating a task proposal."""
    reply = _known_answer(message)
    engine = "rules"

    if reply is None and llm_service.available():
        model_reply = llm_service.complete(
            SYSTEM,
            f"User question: {message}\nAnswer briefly and honestly.",
            json_mode=False,
        )
        if model_reply:
            reply = model_reply.strip()[:700]
            engine = "model"

    reply = reply or DEFAULT
    return {
        "agent": NAME,
        "reply": reply,
        "requires_confirmation": False,
        "payload": {"intent": "general", "engine": engine},
    }
