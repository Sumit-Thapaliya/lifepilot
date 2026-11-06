"""Shared pytest setup: every test runs against a throwaway database."""

from __future__ import annotations

import os

import pytest

from backend import database

# Tests drive the scheduler explicitly; never let a background clock interfere.
os.environ["LIFEPILOT_TICK"] = "0"


@pytest.fixture(autouse=True, scope="session")
def _temporary_database(tmp_path_factory):
    """Redirect the whole application at a temp SQLite file for the session."""
    temp_db = tmp_path_factory.mktemp("lifepilot") / "test.db"
    database.DB_PATH = temp_db  # used by db_path() when no env override is set
    os.environ["LIFEPILOT_DB"] = str(temp_db)
    database.init_db()
    yield temp_db
    if temp_db.exists():
        temp_db.unlink()


@pytest.fixture(autouse=True)
def _clean_tables():
    """Start each test from empty tables so counts are deterministic."""
    with database.connect() as connection:
        for table in ("tasks", "bills", "reminders", "daily_plans", "user_memory", "deliveries"):
            connection.execute(f"DELETE FROM {table}")
    yield
