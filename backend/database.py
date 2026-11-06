"""SQLite storage for LifePilot.

One small local database, five tables, no ORM and no external service. The
path can be overridden with the ``LIFEPILOT_DB`` environment variable, which
tests use to point at a temporary file.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "lifepilot.db"


def db_path() -> Path:
    """Resolve the database path, honouring the LIFEPILOT_DB override."""
    override = os.getenv("LIFEPILOT_DB")
    return Path(override) if override else DEFAULT_DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    title             TEXT    NOT NULL,
    deadline          TEXT,
    category          TEXT    NOT NULL DEFAULT 'personal',
    priority          INTEGER NOT NULL DEFAULT 3,
    notes             TEXT    NOT NULL DEFAULT '',
    suggested_time    TEXT,
    context           TEXT    NOT NULL DEFAULT '',
    estimated_minutes INTEGER NOT NULL DEFAULT 30,
    status            TEXT    NOT NULL DEFAULT 'pending',
    postponed_to      TEXT,
    approved          INTEGER NOT NULL DEFAULT 1,
    created_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bills (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    amount     REAL    NOT NULL DEFAULT 0,
    due_date   TEXT,
    recurrence TEXT    NOT NULL DEFAULT 'monthly',
    approved   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reminders (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    message   TEXT    NOT NULL,
    remind_at TEXT,
    kind      TEXT    NOT NULL DEFAULT 'general',
    sent      INTEGER NOT NULL DEFAULT 0,
    approved  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS deliveries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    text       TEXT NOT NULL,
    channel    TEXT,
    delivered  INTEGER NOT NULL DEFAULT 0,
    sent_at    TEXT NOT NULL,
    UNIQUE (kind, dedupe_key)
);

CREATE TABLE IF NOT EXISTS daily_plans (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_date  TEXT,
    content    TEXT    NOT NULL,
    approved   INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_memory (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def connect() -> sqlite3.Connection:
    """Open a connection that returns rows as dictionaries."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


# Columns added after the first release. CREATE TABLE IF NOT EXISTS does not
# alter an existing table, so a database created by an older version would throw
# "no such column" the moment new code ran. Tests never caught this because they
# build a fresh database every session; a real user's file persists.
_MIGRATIONS: dict[str, dict[str, str]] = {
    "tasks": {
        "suggested_time": "TEXT",
        "context": "TEXT NOT NULL DEFAULT ''",
    },
}


def _migrate(connection) -> None:
    """Add any missing columns in place. Safe to run on every start."""
    for table, columns in _MIGRATIONS.items():
        existing = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not existing:
            continue  # table does not exist yet; SCHEMA just created it
        for name, ddl in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def init_db() -> None:
    """Create every table if it does not exist, then bring older files up to date."""
    with connect() as connection:
        connection.executescript(SCHEMA)
        _migrate(connection)


def reset_db() -> None:
    """Delete every row. Used by the demo command and by tests.

    ``deliveries`` must be cleared too: it is the scheduler's "already sent"
    ledger. Leaving stale rows behind would silence every future reminder,
    which is exactly the bug this reset is meant to avoid.
    """
    with connect() as connection:
        for table in (
            "tasks",
            "bills",
            "reminders",
            "daily_plans",
            "user_memory",
            "deliveries",
        ):
            connection.execute(f"DELETE FROM {table}")


def reset_outbox() -> None:
    """Empty the local outbox file, if one exists."""
    from .services import deliver_service

    try:
        deliver_service.outbox_path().unlink(missing_ok=True)
    except OSError:
        pass


# Called on import so the CLI works without an explicit initialisation step.
init_db()
