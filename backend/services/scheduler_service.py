"""Scheduler — the part that decides to speak first.

Without this module LifePilot only answers. With it, LifePilot notices things
and messages you:

    * a bill that is close to its due date
    * a task that is due today or overdue
    * the morning briefing, once, at your wake-up time
    * the evening review, once, at your reminder time

Design rules, in order of importance:

1.  **Nobody wakes up to 40 messages.** Every alert is recorded in the
    ``deliveries`` table keyed by (kind, dedupe_key), so a bill reminder is sent
    once per day and a briefing once per day. Re-running the tick is safe.
2.  **The scheduler never changes stored data.** It reads tasks and bills and
    sends text. It does not postpone, complete, or delete anything. Changes
    still go through the proposal/approval path.
3.  **It reports exactly what it did.** ``run_tick`` returns one entry per
    reminder it decided to send, including whether delivery succeeded.
"""

from __future__ import annotations

import os
from datetime import date, datetime, time as dt_time
from typing import Optional

from ..database import connect
from . import deliver_service, reminder_service
from .bill_service import upcoming_bills
from .memory_service import get_value
from .task_service import list_tasks

DEFAULT_BILL_WINDOW = 3
DEFAULT_TASK_WINDOW = 1
QUIET_START = dt_time(0, 0)


# ---------------------------------------------------------------- dedupe store

def ensure_table() -> None:
    """Create the deliveries table if an older database lacks it.

    New databases get it from ``database.SCHEMA``; this exists so a database
    created by a previous version keeps working after an upgrade.
    """
    with connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS deliveries (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                kind       TEXT NOT NULL,
                dedupe_key TEXT NOT NULL,
                text       TEXT NOT NULL,
                channel    TEXT,
                delivered  INTEGER NOT NULL DEFAULT 0,
                sent_at    TEXT NOT NULL,
                UNIQUE (kind, dedupe_key)
            )
            """
        )


def already_sent(kind: str, dedupe_key: str) -> bool:
    ensure_table()
    with connect() as con:
        row = con.execute(
            "SELECT 1 FROM deliveries WHERE kind=? AND dedupe_key=?",
            (kind, dedupe_key),
        ).fetchone()
    return row is not None


def claim(kind: str, dedupe_key: str) -> bool:
    """Atomically reserve this alert. True if we own it, False if already sent.

    Claiming happens *before* delivery and relies on the UNIQUE constraint, so
    two processes ticking at the same moment cannot both send the same
    reminder. INSERT OR IGNORE reports rowcount 0 for the loser.
    """
    ensure_table()
    with connect() as con:
        cursor = con.execute(
            """
            INSERT OR IGNORE INTO deliveries
                (kind, dedupe_key, text, channel, delivered, sent_at)
            VALUES (?,?,?,?,?,?)
            """,
            (
                kind,
                dedupe_key,
                "",
                None,
                0,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        return cursor.rowcount == 1


def record_result(kind: str, dedupe_key: str, text: str, outcome: dict) -> None:
    """Fill in the outcome of a claimed alert, honestly."""
    channels = outcome.get("channels") or []
    delivered = 1 if outcome.get("delivered") and channels else 0
    if outcome.get("channel"):
        label = outcome["channel"]
    elif "outbox" in channels:
        label = "outbox"
    elif channels:
        label = channels[-1]
    else:
        label = "none"
    with connect() as con:
        con.execute(
            """
            UPDATE deliveries
               SET text=?, channel=?, delivered=?
             WHERE kind=? AND dedupe_key=?
            """,
            (text, label, delivered, kind, dedupe_key),
        )


def release(kind: str, dedupe_key: str) -> None:
    """Give a claim back if delivery never happened, so it retries next pass."""
    with connect() as con:
        con.execute(
            "DELETE FROM deliveries WHERE kind=? AND dedupe_key=? AND delivered=0 AND text=''",
            (kind, dedupe_key),
        )


def sent_count() -> int:
    """How many reminders have actually been delivered — from the ledger."""
    ensure_table()
    with connect() as con:
        row = con.execute("SELECT COUNT(*) FROM deliveries WHERE delivered=1").fetchone()
    return int(row[0]) if row else 0


def history(limit: int = 20) -> list[dict]:
    """Most recent deliveries, newest first — proof of what was sent."""
    ensure_table()
    with connect() as con:
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM deliveries ORDER BY id DESC LIMIT ?", (limit,)
            )
        ]


# ------------------------------------------------------------------- settings

def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def bill_window_days() -> int:
    return _env_int("LIFEPILOT_BILL_WINDOW", DEFAULT_BILL_WINDOW)


def task_window_days() -> int:
    """How many days ahead to warn about a task. 1 = today, tomorrow, overdue."""
    return _env_int("LIFEPILOT_TASK_WINDOW", DEFAULT_TASK_WINDOW)


def _memory_time(key: str, default: str) -> str:
    value = get_value(key) or default
    return str(value)


def due_now(now: datetime) -> bool:
    """True if ``now`` is at or past the configured reminder time."""
    reminder = _memory_time("reminder_time", "20:30")
    try:
        hour, minute = (int(part) for part in reminder.split(":")[:2])
    except (ValueError, AttributeError):
        return False
    return now.time() >= dt_time(hour, minute)


def morning_due_now(now: datetime) -> bool:
    """True if ``now`` is at or past the configured wake-up time."""
    wake = _memory_time("wake_up_time", "06:30")
    try:
        hour, minute = (int(part) for part in wake.split(":")[:2])
    except (ValueError, AttributeError):
        return False
    return now.time() >= dt_time(hour, minute)


# ------------------------------------------------------------------- builders

def _bill_alerts(today: date) -> list[dict]:
    """One alert per bill inside the window."""
    alerts = []
    for bill in upcoming_bills(within_days=bill_window_days()):
        days = bill.get("days_until_due")
        if days is None or days < 0:
            continue
        name = bill["name"]
        amount = bill["amount"]
        if days <= 0:
            lead = f"Your {name} bill ({amount:,.0f}) is due today."
        else:
            lead = (
                f"Your {name} bill ({amount:,.0f}) is due in {days} day"
                f"{'s' if days != 1 else ''}."
            )
        alerts.append(
            {
                "kind": "bill",
                "dedupe_key": f"{bill['id']}:{today.isoformat()}",
                "text": (
                    f"{lead} Have you paid it?\n"
                    f"Reply 'pay {name.lower()}' to mark it handled, "
                    f"or 'postpone {name.lower()}' to push it back."
                ),
            }
        )
    return alerts


def _task_alerts(today: date) -> list[dict]:
    """One alert per task that is overdue, due today, or due within the window.

    A reminder app that only speaks on the due date is useless: by then the day
    is already gone. The default window warns one day ahead as well.
    """
    alerts = []
    window = task_window_days()
    for task in list_tasks(status="pending"):
        deadline = task.get("deadline")
        if not deadline:
            continue
        try:
            due = date.fromisoformat(deadline[:10])
        except ValueError:
            continue
        days = (due - today).days
        if days > window:
            continue

        title = task["title"]
        if days == 0:
            lead = f'"{title}" is due today.'
        elif days < 0:
            lead = f'"{title}" was due {abs(days)} day(s) ago.'
        elif days == 1:
            lead = f'"{title}" is due tomorrow.'
        else:
            lead = f'"{title}" is due in {days} days.'

        alerts.append(
            {
                "kind": "task",
                "dedupe_key": f"{task['id']}:{today.isoformat()}:{days}",
                "text": f"{lead} Have you completed it?",
            }
        )
    return alerts


def _briefing_alert(now: datetime, kind: str) -> dict:
    today = now.date()
    if kind == "morning":
        payload = reminder_service.morning_briefing()
    else:
        payload = reminder_service.evening_review()
    return {
        "kind": f"briefing_{kind}",
        "dedupe_key": today.isoformat(),
        "text": payload["message"],
    }


# ----------------------------------------------------------------------- tick

def run_tick(
    now: Optional[datetime] = None,
    force: bool = False,
    include_briefings: bool = True,
) -> dict:
    """One scheduler pass.

    ``force`` ignores the clock (useful for demos and tests) but still respects
    the once-per-day dedupe, so running it twice does not double-send.

    ``now`` shifts which day the dedupe keys belong to and whether a briefing
    is considered due. It does NOT change the wording of a briefing: the
    underlying services always describe the real current date. In normal
    operation ``now`` is not passed, so everything agrees.
    """
    now = now or datetime.now()
    today = now.date()

    candidates: list[dict] = []
    candidates.extend(_task_alerts(today))
    candidates.extend(_bill_alerts(today))

    if include_briefings:
        if force or morning_due_now(now):
            candidates.append(_briefing_alert(now, "morning"))
        if force or due_now(now):
            candidates.append(_briefing_alert(now, "evening"))

    results = []
    for candidate in candidates:
        kind = candidate["kind"]
        key = candidate["dedupe_key"]
        # Claim first: if another process already owns this alert, skip it.
        if not claim(kind, key):
            continue
        try:
            outcome = deliver_service.deliver(
                kind, candidate["text"], now.isoformat(timespec="seconds")
            )
        except Exception as exc:  # delivery blew up — give the claim back
            release(kind, key)
            results.append(
                {
                    "kind": kind,
                    "text": candidate["text"],
                    "delivered": False,
                    "channels": [],
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        record_result(kind, key, candidate["text"], outcome)
        if not outcome.get("delivered"):
            # Nothing reached any channel; allow a retry on the next pass.
            with connect() as con:
                con.execute(
                    "DELETE FROM deliveries WHERE kind=? AND dedupe_key=?",
                    (kind, key),
                )
        results.append(
            {
                "kind": kind,
                "text": candidate["text"],
                "delivered": outcome["delivered"],
                "channels": outcome["channels"],
                "error": outcome["error"],
            }
        )

    return {
        "ran_at": now.isoformat(timespec="seconds"),
        "sent": len(results),
        "messages": results,
        "channel": deliver_service.configured_channel() or "outbox",
        "total_sent": sent_count(),
    }
