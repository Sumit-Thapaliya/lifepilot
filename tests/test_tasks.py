"""Tests for the Capture agent and the task service."""

from __future__ import annotations

from datetime import date, timedelta

from backend.agents import capture_agent
from backend.services import task_service


# ---------------------------------------------------------------------------
# Natural language parsing
# ---------------------------------------------------------------------------


def test_parses_title_deadline_category_and_priority():
    parsed = task_service.parse_task_text("urgent finish biology notes by Friday")
    assert parsed["title"] == "Finish biology notes"
    assert parsed["category"] == "study"
    assert parsed["priority"] == 1
    assert parsed["deadline"] is not None


def test_resolves_relative_dates():
    today = task_service.parse_task_text("pay electricity bill today")
    tomorrow = task_service.parse_task_text("call the bank tomorrow")
    assert today["deadline"] == str(date.today())
    assert tomorrow["deadline"] == str(date.today() + timedelta(days=1))


def test_infers_every_supported_category():
    cases = {
        "revise algebra notes": "study",
        "pay the internet bill": "bill",
        "go to the gym": "health",
        "clean the kitchen": "household",
        "client meeting prep": "work",
        "buy a birthday card": "personal",
    }
    for text, expected in cases.items():
        assert task_service.parse_task_text(text)["category"] == expected, text


def test_estimates_effort_and_respects_explicit_minutes():
    assert task_service.parse_task_text("call the landlord")["estimated_minutes"] == 15
    assert task_service.parse_task_text("write essay for 90 minutes")["estimated_minutes"] == 90


# ---------------------------------------------------------------------------
# The approval gate
# ---------------------------------------------------------------------------


def test_create_task_without_approval_saves_nothing():
    result = task_service.create_task({"text": "urgent revise algebra"}, approved=False)
    assert result["status"] == "pending_approval"
    assert task_service.list_tasks() == []


def test_create_task_with_approval_saves():
    saved = task_service.create_task({"text": "urgent revise algebra"}, approved=True)
    assert saved["id"] is not None
    assert saved["category"] == "study"
    assert len(task_service.list_tasks()) == 1


def test_client_defaults_do_not_clobber_parsed_values():
    """Regression: model_dump() sends title=None and category='personal'.

    Those defaults used to overwrite what the parser inferred, which crashed
    the insert with a NOT NULL constraint error.
    """
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    response = client.post(
        "/tasks", json={"text": "urgent revise algebra tomorrow", "approved": True}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Revise algebra"
    assert body["category"] == "study"
    assert body["priority"] == 1


def test_explicit_values_override_the_parser():
    saved = task_service.create_task(
        {"text": "revise algebra", "category": "work", "priority": 5}, approved=True
    )
    assert saved["category"] == "work"
    assert saved["priority"] == 5


def test_create_task_reports_missing_title_instead_of_crashing():
    result = task_service.create_task({"notes": "nothing useful"}, approved=True)
    assert result["status"] == "error"


def test_api_rejects_task_with_no_title_or_text():
    from fastapi.testclient import TestClient

    from backend.main import app

    client = TestClient(app)
    assert client.post("/tasks", json={"approved": True}).status_code == 422


def test_capture_proposes_then_saves_only_on_yes():
    proposal = capture_agent.propose("submit lab report by Friday")
    assert proposal.requires_confirmation is True
    assert task_service.list_tasks() == [], "proposing must not write"

    result = capture_agent.confirm(proposal, approved=True)
    assert result["saved"]["title"] == "Submit lab report"
    assert len(task_service.list_tasks()) == 1


def test_capture_discard_saves_nothing():
    proposal = capture_agent.propose("clean the kitchen")
    result = capture_agent.confirm(proposal, approved=False)
    assert result["saved"] is None
    assert task_service.list_tasks() == []


def test_photo_proposals_save_only_after_approval():
    proposals = [
        {"title": "Pay water bill", "category": "bill", "priority": 2,
         "deadline": None, "notes": "", "estimated_minutes": 10},
        {"title": "Buy groceries", "category": "household", "priority": 3,
         "deadline": None, "notes": "", "estimated_minutes": 30},
    ]
    saved = capture_agent.save_photo_proposals(proposals)
    assert len(saved["saved"]) == 2
    assert len(task_service.list_tasks()) == 2


# ---------------------------------------------------------------------------
# Approval, edit, postpone, delete
# ---------------------------------------------------------------------------


def test_update_postpone_complete_and_delete():
    task = task_service.create_task({"title": "Read chapter 3", "priority": 2}, approved=True)

    edited = task_service.update_task(task["id"], {"title": "Read chapter 4", "priority": 1})
    assert edited["title"] == "Read chapter 4"
    assert edited["priority"] == 1

    moved = task_service.postpone_task(task["id"], "2026-12-01")
    assert moved["status"] == "postponed"
    assert moved["postponed_to"] == "2026-12-01"

    done = task_service.complete_task(task["id"])
    assert done["status"] == "done"

    assert task_service.delete_task(task["id"], approved=False)["status"] == "pending_approval"
    assert len(task_service.list_tasks()) == 1, "unapproved delete must not remove anything"

    task_service.delete_task(task["id"], approved=True)
    assert task_service.list_tasks() == []


# ---------------------------------------------------------------------------
# Photo flow through the chat router
# ---------------------------------------------------------------------------


def test_router_handles_photo_results_without_saving():
    from backend.agents import capture_agent, router

    ocr_result = {
        "ocr_available": True,
        "proposals": [
            {"title": "Pay water bill", "category": "bill", "deadline": None,
             "priority": 2, "notes": "", "estimated_minutes": 10},
            {"title": "Buy groceries", "category": "household", "deadline": None,
             "priority": 3, "notes": "", "estimated_minutes": 30},
        ],
    }
    response = router.route("", photo_result=ocr_result)
    assert response["agent"] == "Capture"
    assert len(response["pending_photo"]) == 2
    assert task_service.list_tasks() == [], "a photo proposal must not save anything"

    saved = capture_agent.save_photo_proposals(response["pending_photo"])
    assert len(saved["saved"]) == 2


def test_router_handles_unreadable_photo():
    from backend.agents import router

    response = router.route("", photo_result={"proposals": [], "reply": "I could not read that photo."})
    assert response["agent"] == "Capture"
    assert "could not read" in response["reply"].lower()


# ---------------------------------------------------------------------------
# Plain language: an eight-year-old should be able to use this.
# ---------------------------------------------------------------------------

PLAIN_SENTENCES = [
    # (what a child says, expected category, expected deadline-ish)
    ("play games with my friends on saturday", "personal", "2026"),
    ("i have to do my homework today", "study", "2026"),
    ("feed the dog", "household", None),
    ("walk the dog", "health", None),   # walking a dog is exercise; either answer is fair
    ("clean my room", "household", None),
    ("football practice tomorrow at 4", "personal", "2026"),
    ("call grandma on sunday", "personal", "2026"),
    ("buy a birthday present for mom", "personal", None),
]


def test_plain_language_is_understood():
    """Everyday sentences, not developer phrasing."""
    from backend.services.task_service import parse_task_text

    for text, category, deadline_start in PLAIN_SENTENCES:
        parsed = parse_task_text(text)
        assert parsed["category"] == category, f"{text!r} -> {parsed['category']}, wanted {category}"
        if deadline_start:
            assert parsed["deadline"] and parsed["deadline"].startswith(deadline_start), (
                f"{text!r} lost its date: {parsed['deadline']}"
            )
        assert parsed["title"], f"{text!r} produced an empty title"


def test_category_matching_uses_whole_words():
    """"work" must not match inside "homework"; "fee" must not match "feed"."""
    from backend.services.task_service import parse_task_text

    assert parse_task_text("do my homework")["category"] == "study"
    assert parse_task_text("feed the dog")["category"] == "household"
    assert parse_task_text("pay the fees")["category"] == "bill"


def test_clock_time_does_not_land_in_the_title():
    from backend.services.task_service import parse_task_text

    parsed = parse_task_text("football practice tomorrow at 4")
    assert parsed["title"] == "Football practice"
    assert "  " not in parsed["title"], "double space left behind"


def test_a_non_date_word_is_not_a_deadline():
    """"before bed" is not a date. Saying so beats inventing one."""
    from backend.services.task_service import parse_task_text

    assert parse_task_text("read a book before bed")["deadline"] is None


def test_pets_and_money_are_never_low_priority():
    from backend.services.task_service import parse_task_text

    assert parse_task_text("feed the dog")["priority"] <= 2
    assert parse_task_text("pay the electricity bill")["priority"] <= 2


# ------------------------------------------------------------- migrations

def test_an_old_database_gains_the_new_columns(tmp_path):
    """A user's existing file must survive an upgrade.

    CREATE TABLE IF NOT EXISTS silently skips an existing table, so new columns
    were missing and POST /tasks returned 500 on any real installation. Tests
    only passed because they always start from an empty file.
    """
    import sqlite3

    from backend import database

    old = tmp_path / "old.db"
    con = sqlite3.connect(old)
    con.executescript(
        """
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            deadline TEXT,
            category TEXT NOT NULL DEFAULT 'personal',
            priority INTEGER NOT NULL DEFAULT 3,
            notes TEXT NOT NULL DEFAULT '',
            estimated_minutes INTEGER NOT NULL DEFAULT 30,
            status TEXT NOT NULL DEFAULT 'pending',
            postponed_to TEXT,
            approved INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    con.execute("INSERT INTO tasks (title) VALUES ('An old task')")
    con.commit()
    con.close()

    original = database.DB_PATH
    database.DB_PATH = old
    import os

    os.environ["LIFEPILOT_DB"] = str(old)
    try:
        database.init_db()
        with database.connect() as check:
            columns = {row[1] for row in check.execute("PRAGMA table_info(tasks)")}
            assert {"suggested_time", "context"} <= columns
            # The old row survived and just has empty new fields.
            row = check.execute("SELECT title, context FROM tasks").fetchone()
            assert row[0] == "An old task"
            assert row[1] == ""
    finally:
        database.DB_PATH = original
        os.environ["LIFEPILOT_DB"] = str(original)
