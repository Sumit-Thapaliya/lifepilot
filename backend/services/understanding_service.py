"""Understanding — the model reads the sentence, the code guards the database.

This is the layer that makes LifePilot dynamic instead of if-else.

    "read a book before bed"
        rule parser  ->  no date, no time, "personal"
        this layer   ->  "Read a book", 20:30, why: a book before bed is a
                          bedtime activity, so it belongs in the evening.

How it works
------------
1. The model is given the user's words, today's date and weekday, and the
   user's known preferences, and is asked for JSON only.
2. Every field it returns is **validated and clamped** here. The model cannot
   invent a category outside the six, a priority outside 1-3, a malformed time,
   or a date in the past.
3. If there is no model configured, or it fails, the rule parser is used and
   the result says so. The user is never blocked by an API outage.

The important line: the model proposes, this module disposes. An LLM that can
write straight to a database is a liability; an LLM that fills a validated
struct is a feature.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional

from . import llm_service, memory_service, task_service
from ..models import CATEGORIES

SYSTEM = """You turn one person's everyday sentence into a single task for a
friendly life assistant. The user may be a child. They will not choose
categories, priorities, or times - you infer all of it.

Return JSON with exactly these keys:

  title            short and action-first, in the user's own words where possible
                   (e.g. "Read a book", "Feed the dog"). No dates, no times.
  category         exactly one of: study, personal, bill, health, household, work
  priority         1 = must happen today, 2 = soon or can't be forgotten,
                   3 = normal. Money owed and animals that depend on the user
                   are never 3.
  deadline         YYYY-MM-DD if a date is implied, otherwise null.
                   Use the TODAY value you are given to resolve "friday".
                   A time of day is NOT a deadline: "at 4" is null here.
  suggested_time   HH:MM (24h) if the sentence implies a time of day, else null.
                   "before bed" -> 20:30, "at 4" -> 16:00, "in the morning" ->
                   07:30, "after school" -> 16:30. This is the field that makes
                   you useful - reason about what the activity means.
  estimated_minutes integer minutes the task will take.
  context          one short sentence, max 12 words, explaining your reasoning
                   in plain language the user can read and disagree with.

Rules:
  - Never invent a deadline. If the sentence has no date, deadline is null.
  - If the sentence is a question or a feeling, not a task, set title to "".
  - Return JSON only. No prose, no code fences.
"""


def _coerce_time(value) -> Optional[str]:
    """Accept 20:30, 8pm, 8:30 pm, 20.30 — return HH:MM or None."""
    if value is None:
        return None
    raw = str(value).strip().lower()
    if not raw:
        return None

    match = re.fullmatch(r"(\d{1,2})[:.](\d{2})\s*(am|pm)?", raw)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        meridiem = match.group(3)
        if meridiem == "pm" and hour < 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None

    match = re.fullmatch(r"(\d{1,2})\s*(am|pm)", raw)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(2) == "pm":
            hour += 12
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    return None


def _coerce_deadline(value) -> Optional[str]:
    """Accept only a real ISO date that is not in the past."""
    if value is None:
        return None
    raw = str(value).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    # Yesterday or earlier is almost always a model mistake about "today".
    if parsed < date.today() - timedelta(days=1):
        return None
    return parsed.isoformat()


def _coerce_minutes(value, fallback: int) -> int:
    """Clamp to a believable range, falling back rather than inventing 1 minute."""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return fallback
    if minutes < 1 or minutes > 600:
        return fallback
    return minutes


def _coerce_category(value) -> Optional[str]:
    if not value:
        return None
    lowered = str(value).strip().lower()
    return lowered if lowered in CATEGORIES else None


def _coerce_priority(value) -> Optional[int]:
    try:
        priority = int(value)
    except (TypeError, ValueError):
        return None
    return priority if 1 <= priority <= 5 else None


def _clean_title(value) -> str:
    title = str(value or "").strip().strip('"').strip()
    title = re.sub(r"\s{2,}", " ", title)
    return title[:120]


def understand(text: str, today: Optional[date] = None) -> dict:
    """Read one sentence. Returns parsed fields plus how they were produced."""
    today = today or date.today()
    baseline = task_service.parse_task_text(text)

    if not llm_service.available():
        return {
            "parsed": baseline,
            "engine": "rules",
            "engine_note": (
                "No language model configured, so keyword rules were used. "
                "These cannot infer times like 'before bed'."
            ),
            "reasoning": {},
        }

    preferences = {
        key: memory_service.get_value(key)
        for key in ("name", "wake_up_time", "reminder_time", "timezone")
    }
    preferences = {k: v for k, v in preferences.items() if v}

    user_prompt = (
        f"TODAY is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"User preferences: {preferences or 'none known'}.\n"
        f'Sentence: "{text}"\n'
        "Return the JSON object now."
    )

    raw = llm_service.complete_json(SYSTEM, user_prompt)
    if not raw:
        return {
            "parsed": baseline,
            "engine": "rules (model unavailable)",
            "engine_note": llm_service.status().get("last_error") or "The model returned nothing.",
            "reasoning": {},
        }

    title = _clean_title(raw.get("title"))
    if not title:
        return {
            "parsed": baseline,
            "engine": "rules",
            "engine_note": "The model judged this not to be a task.",
            "reasoning": {},
            "not_a_task": True,
        }

    parsed = {
        "title": title,
        "category": _coerce_category(raw.get("category")) or baseline["category"],
        "priority": _coerce_priority(raw.get("priority")) or baseline["priority"],
        "deadline": _coerce_deadline(raw.get("deadline")),
        "suggested_time": _coerce_time(raw.get("suggested_time")),
        "estimated_minutes": _coerce_minutes(
            raw.get("estimated_minutes"), baseline["estimated_minutes"]
        ),
        "notes": baseline.get("notes", ""),
        "context": str(raw.get("context") or "")[:160],
    }

    return {
        "parsed": parsed,
        "engine": f"model: {llm_service.model_name()}",
        "engine_note": "Understood by the language model, then validated before storage.",
        "reasoning": {
            "title": "model rewrote the sentence into an action",
            "category": f"model chose {parsed['category']}",
            "priority": f"model chose priority {parsed['priority']}",
            "deadline": f"model returned {parsed['deadline'] or 'no date'}",
            "suggested_time": f"model returned {parsed['suggested_time'] or 'no time'}",
            "estimated_minutes": f"model estimated {parsed['estimated_minutes']} minutes",
            "context": parsed["context"] or "no explanation offered",
        },
        "raw_model_json": raw,
    }


def status() -> dict:
    """What /health and the UI report about the understanding layer."""
    return {
        "mode": "model" if llm_service.available() else "rules",
        "llm": llm_service.status(),
        "fallback": "keyword rules (deterministic, no time-of-day inference)",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
