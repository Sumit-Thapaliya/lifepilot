"""Reminder service: stored reminders, morning briefing, and evening review.

Mock weather is deliberately hard-coded so the project needs no paid API. The
morning briefing uses the user's stored ``wake_up_time`` and the evening
review reports completed, postponed, and tomorrow's top three.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..database import connect
from .bill_service import due_reminder_text, upcoming_bills
from .memory_service import get_value
from .task_service import list_tasks

# Mock weather: no external weather API is used anywhere in this project.
MOCK_WEATHER = {"summary": "Clear skies", "high_c": 24, "low_c": 15}


# ---------------------------------------------------------------------------
# Stored reminders
# ---------------------------------------------------------------------------


def create_reminder(data: dict) -> dict:
    """Persist a reminder so it survives restarts."""
    with connect() as con:
        cursor = con.execute(
            "INSERT INTO reminders (message, remind_at, kind, approved) VALUES (?,?,?,?)",
            (
                data["message"],
                data.get("remind_at"),
                data.get("kind", "general"),
                int(data.get("approved", True)),
            ),
        )
        row = con.execute("SELECT * FROM reminders WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_reminders(kind: str | None = None) -> list[dict]:
    with connect() as con:
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM reminders WHERE (? IS NULL OR kind=?)"
                " ORDER BY COALESCE(remind_at, '9999-12-31')",
                (kind, kind),
            )
        ]


def mark_sent(reminder_id: int) -> dict | None:
    with connect() as con:
        con.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
        row = con.execute("SELECT * FROM reminders WHERE id=?", (reminder_id,)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Morning briefing
# ---------------------------------------------------------------------------


def morning_briefing() -> dict:
    """Greeting, today's top three, bills due soon, and mock weather."""
    tasks = [t for t in list_tasks() if t["status"] == "pending"]
    top_three = tasks[:3]
    bills = upcoming_bills(within_days=7)

    lines = [
        f"Good morning. It's {date.today().strftime('%A %d %B')}.",
        f"Weather: {MOCK_WEATHER['summary']}, {MOCK_WEATHER['low_c']}–{MOCK_WEATHER['high_c']}°C (mock).",
    ]
    if top_three:
        lines.append("Today's top three:")
        lines.extend(f"  {i}. {t['title']} — {t['category']}, due {t['deadline'] or 'no date'}"
                     for i, t in enumerate(top_three, 1))
    else:
        lines.append("No open tasks. Say 'add a task …' to capture something.")

    if bills:
        lines.append("Bills to watch:")
        lines.extend(f"  - {due_reminder_text(b)}" for b in bills[:3])

    return {
        "type": "morning",
        "wake_up_time": get_value("wake_up_time"),
        "reminder_time": get_value("reminder_time"),
        "top_priorities": top_three,
        "bills_due_soon": bills,
        "weather": MOCK_WEATHER,
        "message": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Evening review
# ---------------------------------------------------------------------------


def evening_review() -> dict:
    """Completed, postponed, and tomorrow's top three priorities."""
    tasks = list_tasks()
    completed = [t for t in tasks if t["status"] == "done"]
    postponed = [t for t in tasks if t["status"] == "postponed"]
    pending = [t for t in tasks if t["status"] == "pending"]

    tomorrow = str(date.today() + timedelta(days=1))
    tomorrow_tasks = [t for t in pending if t.get("deadline") in (tomorrow, None)][:3]
    if not tomorrow_tasks:
        tomorrow_tasks = pending[:3]

    lines = ["Evening review."]
    lines.append(
        f"Completed today: {', '.join(t['title'] for t in completed) if completed else 'nothing logged'}"
    )
    lines.append(
        f"Postponed: {', '.join(t['title'] for t in postponed) if postponed else 'nothing'}"
    )
    lines.append("Tomorrow's top three:")
    if tomorrow_tasks:
        lines.extend(f"  {i}. {t['title']}" for i, t in enumerate(tomorrow_tasks, 1))
    else:
        lines.append("  Nothing planned yet.")

    return {
        "type": "evening",
        "completed": completed,
        "postponed": postponed,
        "tomorrow_top_three": tomorrow_tasks,
        "message": "\n".join(lines),
    }


# ---------------------------------------------------------------------------
# Bill due-date reminders
# ---------------------------------------------------------------------------


def bill_due_reminders(days_before: int = 3) -> dict:
    """Build reminder text for every bill approaching its due date.

    Nothing is sent and no task is changed — the Reminder agent posts this and
    waits for the user before rescheduling anything.
    """
    bills = [
        b for b in upcoming_bills(within_days=days_before)
        if (b.get("days_until_due") or 0) >= 0
    ]
    lines = [due_reminder_text(b, days_before) for b in bills]
    return {
        "type": "bill_reminders",
        "count": len(bills),
        "bills": bills,
        "message": "\n".join(lines) if lines else "No bills due in the next few days.",
        "sent": False,
    }


# Compatibility alias kept for existing imports.
briefing = morning_briefing
