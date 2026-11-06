"""Tests for bills, reminders, briefings, memory, and the API surface."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient

from backend.agents import reminder_agent
from backend.main import app
from backend.services import bill_service, memory_service, reminder_service, task_service

client = TestClient(app)


# ---------------------------------------------------------------------------
# Bills
# ---------------------------------------------------------------------------


def test_creates_and_lists_bills():
    created = bill_service.create_bill({"name": "Internet", "amount": 1200,
                                        "due_date": "2026-11-15", "recurrence": "monthly"})
    assert created["id"] is not None
    assert created["name"] == "Internet"

    listed = bill_service.list_bills()
    assert len(listed) == 1
    assert listed[0]["amount"] == 1200


def test_counts_days_until_due():
    soon = str(date.today() + timedelta(days=3))
    assert bill_service.days_until(soon) == 3
    assert bill_service.days_until("not-a-date") is None
    assert bill_service.days_until(None) is None


def test_upcoming_bills_only_returns_the_window():
    bill_service.create_bill({"name": "Soon", "amount": 100,
                              "due_date": str(date.today() + timedelta(days=2))})
    bill_service.create_bill({"name": "Far", "amount": 900,
                              "due_date": str(date.today() + timedelta(days=90))})
    upcoming = bill_service.upcoming_bills(within_days=7)
    assert [b["name"] for b in upcoming] == ["Soon"]
    assert upcoming[0]["days_until_due"] == 2


def test_overdue_bill_is_reported_as_overdue():
    overdue = {"name": "Rent", "amount": 15000,
               "due_date": str(date.today() - timedelta(days=2))}
    assert "overdue" in bill_service.due_reminder_text(overdue)


def test_mock_bills_are_seeded_once():
    first = bill_service.seed_mock_bills()
    second = bill_service.seed_mock_bills()
    assert len(first) == len(bill_service.MOCK_BILLS)
    assert len(second) == len(first), "seeding twice must not duplicate bills"


# ---------------------------------------------------------------------------
# Reminders and briefings
# ---------------------------------------------------------------------------


def test_reminders_persist():
    created = reminder_service.create_reminder(
        {"message": "Call mother", "remind_at": "2026-11-09", "kind": "personal"}
    )
    assert created["id"] is not None
    listed = reminder_service.list_reminders()
    assert len(listed) == 1
    assert listed[0]["message"] == "Call mother"


def test_morning_briefing_includes_priorities_weather_and_bills():
    task_service.create_task({"title": "Biology notes", "deadline": str(date.today())}, approved=True)
    bill_service.create_bill({"name": "Electricity", "amount": 2450,
                              "due_date": str(date.today() + timedelta(days=2))})

    briefing = reminder_service.morning_briefing()
    assert briefing["type"] == "morning"
    assert briefing["top_priorities"][0]["title"] == "Biology notes"
    assert briefing["bills_due_soon"][0]["name"] == "Electricity"
    assert "weather" in briefing
    assert "mock" in briefing["message"].lower()


def test_evening_review_reports_completed_postponed_and_tomorrow():
    done = task_service.create_task({"title": "Finished", "deadline": str(date.today())}, approved=True)
    task_service.complete_task(done["id"])

    moved = task_service.create_task({"title": "Moved", "deadline": str(date.today())}, approved=True)
    task_service.postpone_task(moved["id"], str(date.today() + timedelta(days=1)))

    task_service.create_task({"title": "Tomorrow one", "deadline": str(date.today() + timedelta(days=1))},
                             approved=True)

    review = reminder_service.evening_review()
    assert review["type"] == "evening"
    assert [t["title"] for t in review["completed"]] == ["Finished"]
    assert [t["title"] for t in review["postponed"]] == ["Moved"]
    assert len(review["tomorrow_top_three"]) <= 3
    assert "Tomorrow's top three" in review["message"]


def test_bill_due_reminders_never_send_anything():
    bill_service.create_bill({"name": "Internet", "amount": 1200,
                              "due_date": str(date.today() + timedelta(days=1))})
    result = reminder_service.bill_due_reminders(days_before=3)
    assert result["count"] == 1
    assert result["sent"] is False, "reminders must not be marked sent automatically"


# ---------------------------------------------------------------------------
# Reminder agent approval gates
# ---------------------------------------------------------------------------


def test_reminder_agent_asks_before_postponing():
    task = task_service.create_task({"title": "Read notes", "deadline": str(date.today())}, approved=True)
    response = reminder_agent.propose_postpone(task["id"], "2026-12-01")
    assert response["requires_confirmation"] is True
    assert task_service.get_task(task["id"])["status"] == "pending", "proposal must not act"


def test_reminder_agent_executes_only_when_approved():
    task = task_service.create_task({"title": "Read notes", "deadline": str(date.today())}, approved=True)
    action = {"action": "postpone", "task_id": task["id"], "postponed_to": "2026-12-01"}

    cancelled = reminder_agent.execute(action, approved=False)
    assert "Nothing" in cancelled["reply"] or "Cancelled" in cancelled["reply"]
    assert task_service.get_task(task["id"])["status"] == "pending"

    reminder_agent.execute(action, approved=True)
    assert task_service.get_task(task["id"])["status"] == "postponed"


def test_reminder_agent_asks_before_deleting():
    task = task_service.create_task({"title": "Temp", "deadline": str(date.today())}, approved=True)
    response = reminder_agent.propose_delete(task["id"])
    assert response["requires_confirmation"] is True
    assert len(task_service.list_tasks()) == 1


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


def test_memory_stores_and_defaults():
    assert memory_service.get_value("wake_up_time") == "07:00"
    memory_service.set_value("wake_up_time", "06:30")
    assert memory_service.get_value("wake_up_time") == "06:30"
    assert "wake_up_time" in memory_service.all_values()


def test_memory_appends_list_values_without_duplicates():
    memory_service.remember_list("study_subjects", "Biology")
    memory_service.remember_list("study_subjects", "Algebra")
    memory_service.remember_list("study_subjects", "Biology")
    assert memory_service.get_value("study_subjects") == "Biology, Algebra"


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


def test_api_propose_does_not_save_then_creates_with_approval():
    proposal = client.post("/tasks/propose", json={"text": "urgent revise algebra tomorrow"})
    assert proposal.status_code == 200
    body = proposal.json()
    assert body["requires_confirmation"] is True
    assert client.get("/tasks").json() == []

    created = client.post("/tasks", json={**body["proposal"], "approved": True})
    assert created.status_code == 201
    assert created.json()["title"] == "Revise algebra"


def test_api_rejects_creation_without_approval():
    response = client.post("/tasks", json={"text": "do something", "approved": False})
    assert response.status_code == 400


def test_api_dashboard_routes_and_briefings():
    assert client.get("/health").json()["status"] == "ok"
    assert client.post("/briefings/morning").json()["type"] == "morning"
    assert client.post("/briefings/evening").json()["type"] == "evening"
    assert client.get("/bills").json() == []


def test_api_plan_and_study_plan():
    task_service.create_task({"title": "A", "deadline": str(date.today())}, approved=True)
    daily = client.post("/plans/daily", json={"approved": True})
    assert daily.json()["plan_id"] is not None
    assert len(daily.json()["content"]["top_priorities"]) == 1

    exam = str(date.today() + timedelta(days=7))
    study = client.post("/plans/study", json={"exam_date": exam, "study_hours": 14})
    assert study.json()["content"]["study_plan"]["hours_per_day"] == 2.0


def test_api_chat_routes_to_the_right_agent():
    """Each call uses its own conversation id so pending proposals do not leak."""
    assert client.post("/chat", json={"message": "plan my day", "sender": "a"}).json()["agent"] == "Planner"
    assert client.post("/chat", json={"message": "morning briefing", "sender": "b"}).json()["agent"] == "Reminder"
    assert client.post("/chat", json={"message": "add a task to buy milk", "sender": "c"}).json()["agent"] == "Capture"


def test_chat_pending_survives_until_answered():
    """A pending plan must not be discarded by an unrelated message."""
    room = {"sender": "room-1"}
    # Planning needs something to plan; with an empty table Planner correctly
    # replies "no open tasks" and raises no proposal.
    task_service.create_task({"title": "Standup", "deadline": str(date.today())}, approved=True)

    first = client.post("/chat", json={"message": "plan my day", **room}).json()
    assert first["requires_confirmation"] is True
    assert client.get("/chat/pending", params={"sender": "room-1"}).json()["pending"] is not None

    other = client.post("/chat", json={"message": "morning briefing", **room}).json()
    assert other["agent"] == "Planner", "an unrelated message must not silently drop the plan"
    assert "unsaved plan" in other["reply"]

    confirmed = client.post("/chat", json={"message": "yes", **room}).json()
    assert "Saved" in confirmed["reply"]
    assert client.get("/chat/pending", params={"sender": "room-1"}).json()["pending"] is None


def test_chat_pending_can_be_abandoned():
    client.post("/chat", json={"message": "plan my day", "sender": "room-2"})
    client.delete("/chat/pending", params={"sender": "room-2"})
    assert client.get("/chat/pending", params={"sender": "room-2"}).json()["pending"] is None


def test_api_memory_rejects_unknown_keys():
    assert client.put("/memory", json={"key": "wake_up_time", "value": "06:00"}).status_code == 200
    assert client.put("/memory", json={"key": "password", "value": "x"}).status_code == 422
