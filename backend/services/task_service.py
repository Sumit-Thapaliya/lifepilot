"""Task service: natural-language parsing, approval gate, and storage.

The single most important rule in this file: ``create_task`` does nothing
unless ``approved=True``. Agents call it only after the user says yes.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from ..database import connect
from ..models import CATEGORIES

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _has_word(text_lower: str, word: str) -> bool:
    """True only for a whole-word match.

    Plain ``in`` was silently wrong: "work" matched inside "homework" and "fee"
    matched inside "feed the dog", which categorised a pet chore as a bill.
    Word boundaries fix the whole class of bug.
    """
    if not word:
        return False
    pattern = r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?![a-z0-9])"
    return re.search(pattern, text_lower) is not None

# Leading filler: "add a task to ", "remember to ", "track ", "create task: "
_PREFIX = re.compile(
    r"^\s*(?:add|create|remember|track|new|log)\s+"
    r"(?:a\s+|an\s+)?(?:task|reminder|item|bill)?\s*(?:to\s+|:|,|-)?\s*",
    re.I,
)

# Deadline clause: "by Friday", "on the 15th", "due tomorrow"
_DEADLINE = re.compile(r"\s+(?:by|on|due|before)\s+([^,.;]+)", re.I)

# Words that should not survive into the task title.
_NOISE = re.compile(
    r"\b(?:remind\s+me\s+to|please|urgent|asap|immediately|important|soon"
    r"|high\s+priority|low\s+priority|today|tonight|tomorrow|next\s+week"
    r"|on\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|by\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r"|(?:at|around)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b",
    re.I,
)

# Vocabulary hints used to infer a category when none is stated explicitly.
_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "study": (
        "exam", "revise", "revision", "assignment", "lecture", "notes", "biology",
        "algebra", "physics", "chemistry", "lab report", "homework", "study",
        "syllabus", "class", "course", "quiz", "essay", "read chapter",
    ),
    "bill": (
        "bill", "rent", "invoice", "electricity", "internet", "water bill",
        "payment", "recharge", "subscription", "fee", "fees", "installment",
        "tuition", "school fee",
    ),
    "health": (
        "gym", "doctor", "medicine", "walk", "workout", "run", "sleep", "dentist",
        "checkup", "yoga", "health", "hospital", "vitamin",
    ),
    "household": (
        "clean", "laundry", "groceries", "repair", "landlord", "kitchen", "house",
        "room", "plumber", "dishes", "trash", "shopping",
    ),
    "work": (
        "meeting", "client", "boss", "office", "deadline", "report", "presentation",
        "email", "colleague", "shift", "interview", "resume", "standup", "invoice",
        "timesheet", "presentation", "onboarding",
    ),
}

# Extra vocabulary added after testing real phrasing against the parser.
_CATEGORY_HINTS["household"] = _CATEGORY_HINTS["household"] + (
    "washing machine", "fridge", "leak", "fix", "mend", "tidy", "vacuum", "garbage",
        "dog", "cat", "pet", "feed", "walk the dog", "vet", "litter", "puppy", "kitten",
)
_CATEGORY_HINTS["personal"] = (
    "birthday", "gift", "passport", "bank", "visa", "renew", "book", "appointment",
    "travel", "trip", "mom", "dad", "family", "friend", "call",
)

# Words that mark something as a task at all, used by explain_parse.
PRIORITY_WORDS = {
    1: ("urgent", "today", "tonight", "asap", "immediately", "right now", "now"),
    2: ("important", "soon", "tomorrow", "high priority", "don't forget", "dont forget"),
}

# Rough default effort per category, in minutes.
_EFFORT = {
    "study": 45,
    "work": 60,
    "household": 30,
    "health": 30,
    "bill": 10,
    "personal": 20,
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _next_weekday(name: str) -> str:
    today = date.today()
    delta = (WEEKDAYS.index(name) - today.weekday()) % 7 or 7
    return str(today + timedelta(days=delta))


def _resolve_deadline(raw: str | None) -> str | None:
    """Convert relative phrases into ISO dates where that is unambiguous."""
    if not raw:
        return None
    value = raw.strip().lower()
    if value in ("today", "tonight"):
        return str(date.today())
    if value == "tomorrow":
        return str(date.today() + timedelta(days=1))
    if value == "next week":
        return str(date.today() + timedelta(days=7))
    if value in WEEKDAYS:
        return _next_weekday(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    # Words like "bed" or "the trip" are not dates. Returning them as a
    # deadline produced tasks "due bed" — worse than admitting we don't know.
    if value in ("bed", "school", "work", "lunch", "dinner", "breakfast"):
        return None
    return raw.strip()  # e.g. "the 15th" — keep the words rather than guess


def _infer_category(text: str) -> str:
    lowered = text.lower()
    # A literal category word wins first ("this is a work thing").
    for category in CATEGORIES:
        if _has_word(lowered, category):
            return category
    for category, words in _CATEGORY_HINTS.items():
        if any(_has_word(lowered, word) for word in words):
            return category
    return "personal"


# Everyday things a child or a busy adult genuinely cannot forget.
_MONEY_WORDS = ("rent", "bill", "fee", "fees", "pay", "electricity", "internet", "water",
                "school fee", "tax", "invoice")
_PET_WORDS = ("dog", "cat", "pet", "feed", "vet", "litter", "puppy", "kitten")


def _infer_priority(text: str) -> int:
    lowered = text.lower()
    # Unpaid money and an animal that depends on you outrank a default task.
    if any(_has_word(lowered, w) for w in _MONEY_WORDS):
        return 2
    if any(_has_word(lowered, w) for w in _PET_WORDS):
        return 2
    urgent = ("urgent", "today", "tonight", "asap", "immediately", "right now")
    if any(_has_word(lowered, w) for w in urgent):
        return 1
    soon = ("important", "soon", "tomorrow", "high priority", "before")
    if any(_has_word(lowered, w) for w in soon):
        return 2
    return 3


def _infer_effort(text: str, category: str) -> int:
    lowered = text.lower()
    explicit = re.search(r"(\d{1,3})\s*(?:min|mins|minutes)", lowered)
    if explicit:
        return int(explicit.group(1))
    effort = _EFFORT[category]
    if any(_has_word(lowered, w) for w in ("call", "email", "text", "message", "pray")):
        effort = min(effort, 15)
    if any(_has_word(lowered, w) for w in ("feed", "water", "dog", "cat")):
        effort = min(effort, 10)
    return effort


_CLOCK = re.compile(r"\s*(?:at|around)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", re.I)


def _extract_clock(text: str) -> tuple[str, int | None, int | None]:
    """Pull "at 4" / "at 16:30" out of the title and return it separately."""
    match = _CLOCK.search(text)
    if not match:
        return text, None, None
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = (match.group(3) or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    cleaned = (text[: match.start()] + text[match.end():]).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned, hour, minute


def parse_task_text(text: str) -> dict:
    """Extract title, deadline, category, priority, notes, and effort."""
    raw = text.strip()
    category = _infer_category(raw)
    priority = _infer_priority(raw)

    deadline_match = _DEADLINE.search(raw)
    deadline = _resolve_deadline(deadline_match.group(1) if deadline_match else None)
    if deadline is None:
        lowered = raw.lower()
        if "today" in lowered or "tonight" in lowered:
            deadline = str(date.today())
        elif "tomorrow" in lowered:
            deadline = str(date.today() + timedelta(days=1))

    title = _PREFIX.sub("", raw)
    title = _DEADLINE.split(title)[0]
    title = _NOISE.sub("", title).strip(" .,:-")
    if title:
        title = title[0].upper() + title[1:]

    return {
        "title": title or raw,
        "deadline": deadline,
        "category": category,
        "priority": priority,
        "notes": raw,
        "estimated_minutes": _infer_effort(raw, category),
    }


def explain_parse(text: str) -> dict:
    """Return the parsed task *and* the reason each field came out that way.

    This is what makes a rule-based parser honest: you can see exactly which
    keyword matched, instead of trusting a black box.
    """
    raw = text.strip()
    lowered = raw.lower()
    parsed = parse_task_text(raw)

    # Which category keyword fired?
    matched_category = None
    for category in CATEGORIES:
        if category in lowered:
            matched_category = f'literal category word "{category}"'
            break
    if not matched_category:
        for category, words in _CATEGORY_HINTS.items():
            hit = next((w for w in words if w in lowered), None)
            if hit:
                matched_category = f'keyword "{hit}" → {category}'
                break
    matched_category = matched_category or "no keyword matched → default personal"

    # Which priority trigger fired?
    matched_priority = None
    for level, words in PRIORITY_WORDS.items():
        hit = next((w for w in words if w in lowered), None)
        if hit:
            matched_priority = f'keyword "{hit}" → priority {level}'
            break
    matched_priority = matched_priority or "no trigger → default priority 3"

    # Which deadline pattern fired?
    deadline_match = _DEADLINE.search(raw)
    if deadline_match:
        matched_deadline = f'pattern "by/on/due <...>" → "{deadline_match.group(1).strip()}"'
    elif "today" in lowered or "tonight" in lowered:
        matched_deadline = 'keyword "today" → today'
    elif "tomorrow" in lowered:
        matched_deadline = 'keyword "tomorrow" → tomorrow'
    else:
        matched_deadline = "no date phrase → no deadline"

    prefix = _PREFIX.match(raw)
    matched_prefix = f'stripped "{prefix.group(0).strip()}"' if prefix and prefix.group(0).strip() else "no prefix to strip"

    return {
        "input": raw,
        "parsed": parsed,
        "reasoning": {
            "title": f'{matched_prefix}, then removed filler and the date clause',
            "category": matched_category,
            "priority": matched_priority,
            "deadline": matched_deadline,
            "estimated_minutes": f'default {_EFFORT[parsed["category"]]}m for {parsed["category"]}, adjusted for the verb',
        },
        "engine": "rule-based: regex + keyword tables. No LLM, no network call.",
    }


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


# Fields where an empty/None value from an API client means "not supplied" and
# should therefore be filled in from the parsed text instead of overwriting it.
_UNSET = (None, "", "personal", 3, 30)


def create_task(data: dict, approved: bool = False) -> dict:
    """Save a task only when approved; otherwise return a preview."""
    data = dict(data)

    # When the caller sent free text without a title, parse it first. Explicit
    # values always win, but a client's default category/priority must not
    # clobber what the parser inferred.
    if data.get("text") and not data.get("title"):
        parsed = parse_task_text(data["text"])
        for field in ("title", "deadline", "category", "priority", "notes", "estimated_minutes"):
            if data.get(field) in _UNSET or data.get(field) is None:
                data[field] = parsed[field]
        data.pop("text", None)

    if not data.get("title"):
        return {"status": "error", "detail": "A task needs a title or some text"}

    if not approved:
        return {"status": "pending_approval", "preview": data}

    with connect() as con:
        cursor = con.execute(
            "INSERT INTO tasks"
            " (title, deadline, category, priority, notes, suggested_time,"
            "  context, estimated_minutes, approved)"
            " VALUES (?,?,?,?,?,?,?,?,1)",
            (
                data.get("title", "Untitled task"),
                data.get("deadline"),
                data.get("category", "personal"),
                data.get("priority", 3),
                data.get("notes", ""),
                data.get("suggested_time"),
                data.get("context", ""),
                data.get("estimated_minutes", 30),
            ),
        )
        row = con.execute("SELECT * FROM tasks WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_tasks(status: str | None = None) -> list[dict]:
    """All tasks, soonest deadline first, then priority."""
    with connect() as con:
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM tasks WHERE (? IS NULL OR status=?)"
                " ORDER BY COALESCE(deadline, '9999-12-31'), priority, estimated_minutes",
                (status, status),
            )
        ]


def get_task(task_id: int) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row) if row else None


_EDITABLE = {"title", "deadline", "category", "priority", "notes", "estimated_minutes", "status"}


def update_task(task_id: int, updates: dict) -> dict | None:
    """Edit a task. Only known columns are accepted."""
    values = {k: v for k, v in updates.items() if v is not None and k in _EDITABLE}
    if values:
        with connect() as con:
            assignments = ", ".join(f"{k}=?" for k in values)
            con.execute(f"UPDATE tasks SET {assignments} WHERE id=?", (*values.values(), task_id))
    return get_task(task_id)


def complete_task(task_id: int) -> dict | None:
    return update_task(task_id, {"status": "done"})


def postpone_task(task_id: int, postponed_to: str) -> dict | None:
    with connect() as con:
        con.execute(
            "UPDATE tasks SET status='postponed', postponed_to=? WHERE id=?",
            (postponed_to, task_id),
        )
    return get_task(task_id)


def postpone_to_tomorrow(task_id: int) -> dict | None:
    """Convenience used by the Planner's "suggest what to postpone" flow."""
    return postpone_task(task_id, str(date.today() + timedelta(days=1)))


def delete_task(task_id: int, approved: bool = False) -> dict:
    """Deleting is destructive, so it also requires explicit approval."""
    if not approved:
        return {"status": "pending_approval", "task_id": task_id}
    with connect() as con:
        con.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    return {"deleted": task_id}


def suggest_postponements(limit: int = 2) -> list[dict]:
    """Lowest-priority, least-urgent open tasks — candidates for tomorrow.

    Used by the Planner agent when the day is overbooked. Only a suggestion:
    the agent never postpones anything without approval.
    """
    open_tasks = [t for t in list_tasks() if t["status"] == "pending"]
    ranked = sorted(
        open_tasks,
        key=lambda t: (-t["priority"], t.get("deadline") or "9999-12-31", t["estimated_minutes"]),
    )
    return ranked[:limit]
