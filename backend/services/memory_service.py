"""User preference memory.

A tiny key/value store so the agents can remember things like the user's
wake-up time, preferred reminder time, study subjects, and which bills they
pay. This keeps the chat replies personal without storing anything sensitive:
only preference strings are kept, never message history or personal data.
"""

from __future__ import annotations

import os
from typing import Optional

from ..database import connect
from ..models import MEMORY_KEYS

# Sensible defaults so the agents always have something to work with.
# The timezone comes from the environment when set, because "when is 07:00"
# depends on where the user lives — 07:00 UTC is a different moment from
# 07:00 in Asia/Kathmandu.
def _env_or(name: str, fallback: str) -> str:
    """A blank line in .env means 'not configured', not 'use an empty string'."""
    value = (os.environ.get(name) or "").strip()
    return value or fallback


DEFAULTS: dict[str, str] = {
    "wake_up_time": _env_or("LIFEPILOT_WAKE_UP_TIME", "07:00"),
    "reminder_time": _env_or("LIFEPILOT_REMINDER_TIME", "20:00"),
    "study_subjects": "",
    "bill_names": "",
    "timezone": _env_or("LIFEPILOT_TIMEZONE", "UTC"),
    "name": "there",
}


def set_value(key: str, value: str) -> dict:
    """Store or overwrite one preference."""
    key = key.strip().lower()
    with connect() as con:
        con.execute(
            "INSERT INTO user_memory(key, value) VALUES (?, ?)"
            " ON CONFLICT(key) DO UPDATE SET value=excluded.value,"
            " updated_at=CURRENT_TIMESTAMP",
            (key, str(value)),
        )
    return {"key": key, "value": str(value)}


def get_value(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read one preference, falling back to DEFAULTS then the given default."""
    key = key.strip().lower()
    with connect() as con:
        row = con.execute("SELECT value FROM user_memory WHERE key=?", (key,)).fetchone()
    if row:
        return row["value"]
    if default is not None:
        return default
    return DEFAULTS.get(key)


def all_values() -> dict:
    """Every stored preference merged over the defaults."""
    with connect() as con:
        stored = {r["key"]: r["value"] for r in con.execute("SELECT key, value FROM user_memory")}
    return {**DEFAULTS, **stored}


def remember_list(key: str, item: str) -> dict:
    """Append a value to a comma-separated preference such as study_subjects."""
    current = [part.strip() for part in (get_value(key) or "").split(",") if part.strip()]
    if item.strip() and item.strip().lower() not in [c.lower() for c in current]:
        current.append(item.strip())
    return set_value(key, ", ".join(current))


def forget(key: str) -> dict:
    with connect() as con:
        con.execute("DELETE FROM user_memory WHERE key=?", (key.strip().lower(),))
    return {"deleted": key}


def known_keys() -> tuple[str, ...]:
    """The preference keys the agents are allowed to touch."""
    return MEMORY_KEYS


# Compatibility aliases kept for existing imports.
set_memory = set_value
get_memory = all_values
