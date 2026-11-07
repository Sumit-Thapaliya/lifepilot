"""Understanding — the model reads the sentence, the code guards the database.

This is the layer that makes LifePilot dynamic instead of if-else.

Photo OCR is also classified here: the model decides which lines are real
tasks and which are headings, doodles, or notes. Python still validates every
field before anything can be saved.

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

MAX_PHOTO_TASKS = 10

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

PHOTO_CLASSIFY_SYSTEM = """Classify OCR text from a photo of a handwritten or
printed to-do list. Decide which lines are real tasks to ADD and which lines
are NOT tasks and should be IGNORED. Do not turn the whole page into tasks.

Return JSON with exactly this shape:
  {
    "add": [
      {
        "source_text": "original OCR line",
        "title": "short action title",
        "category": "study|personal|bill|health|household|work",
        "priority": 1|2|3,
        "deadline": "YYYY-MM-DD" or null,
        "suggested_time": "HH:MM" or null,
        "estimated_minutes": 30,
        "reason": "short reason this is a real task"
      }
    ],
    "ignore": [
      {"text": "original OCR line", "reason": "short reason this is not a task"}
    ]
  }

Rules:
  - One object per source line. Do not merge lines.
  - ADD only lines that ask the user to do something.
  - IGNORE headings, dates, page numbers, doodles, checkboxes, and random notes.
  - Never invent a deadline. Use the TODAY value to resolve relative dates.
  - If there are no real tasks, return {"add": [], "ignore": [...]}.
  - Return JSON only. No prose, no code fences.
"""


PHOTO_SYSTEM = """You read OCR text from a photo of a handwritten or printed
to-do list. Your job is to find the actionable tasks and ignore headings,
dates, page numbers, doodles, checkboxes, and random notes.

Return JSON with exactly this shape:
  {"tasks": [{"title": "...", "category": "study|personal|bill|health|household|work",
              "priority": 1|2|3, "deadline": "YYYY-MM-DD" or null,
              "suggested_time": "HH:MM" or null,
              "estimated_minutes": 30, "context": "short reason"}]}

Rules:
  - One object per real task. If there are no real tasks, return {"tasks": []}.
  - Rewrite each title as a short action, but keep the user's meaning.
  - Never invent a deadline. Use the TODAY value to resolve relative dates.
  - If a line is a question, a feeling, or a heading, skip it.
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


PHOTO_ACTION_WORDS = (
    "finish", "pay", "call", "buy", "submit", "read", "write", "clean",
    "review", "book", "send", "pick", "walk", "study", "practice",
    "prepare", "fix", "reply", "email", "meet", "schedule", "order",
    "water", "feed", "wash", "cook", "check", "return", "renew", "print",
    "sign", "file", "update", "plan", "draft", "attend", "visit", "take",
    "make", "do", "bring", "collect", "book", "cancel", "confirm",
)

PHOTO_TASK_HINTS = (
    "bill", "exam", "homework", "assignment", "report", "dentist", "doctor",
    "rent", "meeting", "groceries", "milk", "medicine", "deadline",
)


def _photo_rule_proposals(lines: list[str], limit: int) -> list[dict]:
    """Offline fallback: keep lines that actually look like tasks."""
    proposals: list[dict] = []
    for line in lines:
        cleaned = re.sub(r"^\s*(?:\d+[.)]|[-*•]|\[[ xX]\])\s*", "", line).strip()
        if len(cleaned) < 4:
            continue
        lowered = cleaned.lower()
        if cleaned.isupper() and len(cleaned.split()) <= 3:
            continue
        if "doodle" in lowered or re.match(r"^page\s+\d+", lowered):
            continue
        words = re.findall(r"[a-z]+", lowered)
        if not any(word in PHOTO_ACTION_WORDS for word in words) and not any(
            hint in lowered for hint in PHOTO_TASK_HINTS
        ):
            continue
        parsed = task_service.parse_task_text(cleaned)
        if not parsed["title"]:
            continue
        proposals.append(parsed)
        if len(proposals) >= limit:
            break
    return proposals


def _strip_line_marker(line: str) -> str:
    return re.sub(r"^\s*(?:\d+[.)]|[-*•]|\[[ xX]\])\s*", "", line).strip()


def _normalise_line(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _photo_rule_classification(lines: list[str], limit: int) -> dict:
    """Offline fallback: split OCR lines into real tasks and ignored lines."""
    proposals = _photo_rule_proposals(lines, limit)
    add: list[dict] = []
    for proposal in proposals:
        source = proposal.get("notes") or proposal["title"]
        add.append({
            **proposal,
            "source_text": source,
            "reason": "Contains an action word or a task hint.",
        })

    covered = set()
    for item in add:
        covered.add(_normalise_line(item["source_text"]))
        covered.add(_normalise_line(item["title"]))

    ignore: list[dict] = []
    seen: set[str] = set()
    for line in lines:
        cleaned = _strip_line_marker(line)
        key = _normalise_line(cleaned)
        if not key or key in seen or key in covered:
            continue
        seen.add(key)
        ignore.append({
            "text": cleaned[:160],
            "reason": "Heading, doodle, page number, or non-action line.",
        })
    return {"add": add, "ignore": ignore}


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


def understand_photo_text(text: str, today: Optional[date] = None,
                          limit: int = MAX_PHOTO_TASKS) -> dict:
    """Turn raw OCR text into validated task proposals.

    A configured language model reads the whole page and decides which lines
    are tasks. Every field is validated and clamped in Python. If no model is
    configured, or the model fails, readable lines fall back to keyword rules.
    Nothing is written to the database here.
    """
    today = today or date.today()
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 3]
    baseline = _photo_rule_proposals(lines, limit)
    rules_result = {
        "proposals": baseline,
        "engine": "rules",
        "engine_note": (
            "No language model configured, so local rules kept the OCR lines "
            "that look like actionable tasks."
        ),
        "reasoning": ["keyword rules filtered headings and kept task-like lines"],
    }

    if not llm_service.available():
        return rules_result

    user_prompt = (
        f"TODAY is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"OCR TEXT:\n{text}\n"
        "Return the JSON object now."
    )
    raw = llm_service.complete_json(PHOTO_SYSTEM, user_prompt)
    if not raw:
        fallback = dict(rules_result)
        fallback["engine"] = "rules fallback"
        fallback["engine_note"] = (
            llm_service.status().get("last_error")
            or "The model returned nothing, so keyword rules were used."
        )
        return fallback

    items = raw.get("tasks") if isinstance(raw, dict) else None
    if items is None and isinstance(raw, dict) and "title" in raw:
        items = [raw]
    if not isinstance(items, list):
        fallback = dict(rules_result)
        fallback["engine"] = "rules fallback"
        fallback["engine_note"] = "The model returned an unexpected shape, so keyword rules were used."
        return fallback

    proposals: list[dict] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_text") or item.get("text") or item.get("title") or "")
        base = task_service.parse_task_text(source)
        title = _clean_title(item.get("title") or item.get("text") or source)
        if not title or title.lower() in seen:
            continue
        seen.add(title.lower())
        proposals.append({
            "title": title,
            "category": _coerce_category(item.get("category")) or base["category"],
            "priority": _coerce_priority(item.get("priority")) or base["priority"],
            "deadline": _coerce_deadline(item.get("deadline")) or base["deadline"],
            "suggested_time": _coerce_time(item.get("suggested_time")),
            "estimated_minutes": _coerce_minutes(
                item.get("estimated_minutes"), base["estimated_minutes"]
            ),
            "notes": base.get("notes", "") or source,
            "context": str(item.get("context") or "")[:160],
        })
        if len(proposals) >= limit:
            break

    if not proposals:
        fallback = dict(rules_result)
        fallback["engine"] = "rules fallback"
        fallback["engine_note"] = "The model found no tasks, so keyword rules were used."
        return fallback

    return {
        "proposals": proposals,
        "engine": f"model: {llm_service.model_name()}",
        "engine_note": "The model found the tasks in the OCR text, then Python validated every field.",
        "reasoning": [
            f"model selected {p['title']} as priority {p['priority']}"
            for p in proposals
        ],
        "raw_model_json": raw,
    }


def classify_photo_text(text: str, today: Optional[date] = None,
                        limit: int = MAX_PHOTO_TASKS) -> dict:
    """Decide which OCR lines are real tasks and which are not.

    The configured model explains both decisions. Python validates every
    proposed field and uses deterministic line rules when the model is
    unavailable or returns an unusable shape. Nothing is written to storage.
    """
    today = today or date.today()
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 3]
    rules = _photo_rule_classification(lines, limit)
    rules_result = {
        **rules,
        "engine": "rules",
        "engine_note": (
            "No language model configured, so local rules marked action lines "
            "as tasks and everything else as ignored."
        ),
        "reasoning": ["keyword rules separated action lines from headings and notes"],
    }

    if not llm_service.available():
        return rules_result

    user_prompt = (
        f"TODAY is {today.isoformat()} ({today.strftime('%A')}).\n"
        f"OCR TEXT:\n{text}\n"
        "Return the JSON object now."
    )
    raw = llm_service.complete_json(PHOTO_CLASSIFY_SYSTEM, user_prompt)

    def fallback(note: str) -> dict:
        result = dict(rules_result)
        result["engine"] = "rules fallback"
        result["engine_note"] = note
        return result

    if not raw or not isinstance(raw, dict):
        return fallback(llm_service.status().get("last_error") or "The model returned nothing.")
    add_items = raw.get("add")
    ignore_items = raw.get("ignore")
    if not isinstance(add_items, list) or not isinstance(ignore_items, list):
        return fallback("The model returned an unexpected shape, so keyword rules were used.")

    add: list[dict] = []
    seen_add: set[str] = set()
    for item in add_items:
        if not isinstance(item, dict):
            continue
        raw_source = str(item.get("source_text") or item.get("text") or item.get("title") or "").strip()
        source = _strip_line_marker(raw_source)
        base = task_service.parse_task_text(source)
        raw_title = str(item.get("title") or item.get("text") or source)
        title = _clean_title(_strip_line_marker(raw_title))
        key = _normalise_line(title)
        if not title or key in seen_add:
            continue
        seen_add.add(key)
        reason = str(
            item.get("reason") or item.get("context")
            or "The model identified this as an actionable task."
        )[:160]
        add.append({
            "title": title,
            "category": _coerce_category(item.get("category")) or base["category"],
            "priority": _coerce_priority(item.get("priority")) or base["priority"],
            "deadline": _coerce_deadline(item.get("deadline")) or base["deadline"],
            "suggested_time": _coerce_time(item.get("suggested_time")),
            "estimated_minutes": _coerce_minutes(
                item.get("estimated_minutes"), base["estimated_minutes"]
            ),
            "notes": base.get("notes", "") or source,
            "context": reason,
            "reason": reason,
            "source_text": source or title,
        })
        if len(add) >= limit:
            break

    model_ignore: dict[str, str] = {}
    for item in ignore_items:
        if not isinstance(item, dict):
            continue
        raw_ignore = str(item.get("text") or item.get("source_text") or "")
        key = _normalise_line(_strip_line_marker(raw_ignore))
        if not key:
            continue
        model_ignore[key] = str(item.get("reason") or "Not an actionable task.")[:160]

    covered = set()
    for item in add:
        covered.add(_normalise_line(item["source_text"]))
        covered.add(_normalise_line(item["title"]))

    ignore: list[dict] = []
    seen_ignore: set[str] = set()
    for line in lines:
        cleaned = _strip_line_marker(line)
        key = _normalise_line(cleaned)
        if not key or key in seen_ignore or key in covered:
            continue
        seen_ignore.add(key)
        ignore.append({
            "text": cleaned[:160],
            "reason": model_ignore.get(key, "Not marked as a task by the model."),
        })
    for key, reason in model_ignore.items():
        if key not in seen_ignore and key not in covered:
            seen_ignore.add(key)
            ignore.append({"text": key[:160], "reason": reason})

    if not add and not ignore:
        return fallback("The model returned no classification, so keyword rules were used.")

    return {
        "add": add,
        "ignore": ignore,
        "engine": f"model: {llm_service.model_name()}",
        "engine_note": (
            "The model classified each OCR line as a task or not a task, "
            "then Python validated every proposed field."
        ),
        "reasoning": [
            f"model marked {len(add)} line(s) to add and {len(ignore)} line(s) to ignore"
        ],
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
