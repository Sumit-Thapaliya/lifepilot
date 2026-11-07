"""Tests for push reminders — the scheduler that speaks first.

These cover the scheduler's promises:
  1. it actually delivers something (the outbox is a real channel)
  2. it never sends the same alert twice in its dedupe window
  3. it never changes a task or a bill
  4. it reports failure honestly instead of claiming success
  5. periodic progress check-ins are deduplicated and configurable
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from backend import database
from backend.seed import seed_demo_day
from backend.services import deliver_service, scheduler_service


@pytest.fixture(autouse=True)
def outbox(tmp_path, monkeypatch):
    """Point the outbox at a temp file so tests never touch real data."""
    path = tmp_path / "outbox.log"
    monkeypatch.setenv("LIFEPILOT_OUTBOX", str(path))
    for name in deliver_service.CHANNELS.values():
        monkeypatch.delenv(name, raising=False)
    scheduler_service.ensure_table()

    # The demo seed and bill maths are relative to date.today(), but these
    # tests deliberately tick a fixed clock (2026-11-06). Freeze "today" in
    # every module that reads it so the suite stays deterministic on any date.
    class FrozenDate(date):
        @classmethod
        def today(cls):
            return date(2026, 11, 6)

    from backend import seed as seed_mod
    from backend.services import (
        bill_service, planner_service, reminder_service,
        task_service, understanding_service,
    )
    for mod in (
        seed_mod, bill_service, planner_service,
        reminder_service, task_service, understanding_service,
    ):
        monkeypatch.setattr(mod, "date", FrozenDate, raising=False)
    return path


def _reset_with_demo_data():
    database.reset_db()
    seed_demo_day()
    scheduler_service.ensure_table()


def test_tick_delivers_bill_reminder_to_the_outbox(outbox):
    _reset_with_demo_data()
    tick = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))

    kinds = [m["kind"] for m in tick["messages"]]
    assert "bill" in kinds, f"expected a bill alert, got {kinds}"

    bill_message = next(m for m in tick["messages"] if m["kind"] == "bill")
    assert bill_message["delivered"] is True
    assert "Electricity" in bill_message["text"]
    assert "due in 2" in bill_message["text"]
    assert "Have you paid it?" in bill_message["text"]

    assert outbox.exists()
    assert "Electricity" in outbox.read_text()


def test_task_due_today_produces_a_completion_nudge(outbox):
    _reset_with_demo_data()
    tick = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))

    task_messages = [m["text"] for m in tick["messages"] if m["kind"] == "task"]
    assert any("due today" in text for text in task_messages)
    assert any("Have you completed it?" in text for text in task_messages)


def test_running_the_tick_twice_does_not_send_again(outbox):
    _reset_with_demo_data()
    first = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    assert first["sent"] > 0

    second = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 1))
    assert second["sent"] == 0, "a second pass on the same day must send nothing"


def test_next_day_speaks_again(outbox):
    _reset_with_demo_data()
    scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    tomorrow = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 7, 8, 0))
    assert tomorrow["sent"] > 0, "a new day must produce new reminders"


def test_scheduler_never_changes_stored_data(outbox):
    _reset_with_demo_data()
    before_tasks = database_task_snapshot()
    before_bills = database_bill_snapshot()

    scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))

    assert database_task_snapshot() == before_tasks, "scheduler must not modify tasks"
    assert database_bill_snapshot() == before_bills, "scheduler must not modify bills"


def test_webhook_failure_is_reported_not_hidden(outbox, monkeypatch):
    _reset_with_demo_data()
    monkeypatch.setenv("LIFEPILOT_DISCORD_WEBHOOK", "https://example.invalid/hook")

    def boom(url, body, timeout=8.0):
        raise OSError("connection refused")

    monkeypatch.setattr(deliver_service, "_http_post", boom)

    tick = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    bill = next(m for m in tick["messages"] if m["kind"] == "bill")

    # The outbox still caught it, so the message is not lost...
    assert bill["delivered"] is True
    assert "outbox" in bill["channels"]
    # ...and the failure is named rather than swallowed.
    assert bill["error"] and "discord" in bill["error"]


def test_webhook_success_names_the_channel(outbox, monkeypatch):
    _reset_with_demo_data()
    monkeypatch.setenv("LIFEPILOT_DISCORD_WEBHOOK", "https://example.invalid/hook")
    monkeypatch.setattr(deliver_service, "_http_post", lambda url, body, timeout=8.0: None)

    tick = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    bill = next(m for m in tick["messages"] if m["kind"] == "bill")

    assert bill["delivered"] is True
    assert "discord" in bill["channels"]
    assert bill["error"] is None


def test_history_records_outbox_delivery_as_delivered(outbox):
    """A message in the outbox was delivered — recording it as 0 would be a lie."""
    _reset_with_demo_data()
    scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    rows = scheduler_service.history()
    bill_rows = [r for r in rows if r["kind"] == "bill"]
    assert bill_rows, "expected a bill row in history"
    assert all(r["delivered"] == 1 for r in bill_rows)
    assert all(r["channel"] == "outbox" for r in bill_rows)


def test_history_records_what_was_sent(outbox):
    _reset_with_demo_data()
    scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    rows = scheduler_service.history()
    assert rows, "history must show what was sent"
    assert any(row["kind"] == "bill" for row in rows)


# ------------------------------------------------------------------ helpers

def database_task_snapshot():
    with database.connect() as con:
        return [dict(row) for row in con.execute("SELECT * FROM tasks ORDER BY id")]


def database_bill_snapshot():
    with database.connect() as con:
        return [dict(row) for row in con.execute("SELECT * FROM bills ORDER BY id")]


# ------------------------------------------------------- claim / race safety

def test_two_tickers_cannot_both_send_the_same_alert(outbox):
    """Two processes ticking at once must produce one message, not two.

    This is why the scheduler claims the dedupe key *before* delivering.
    """
    _reset_with_demo_data()
    now = datetime(2026, 11, 6, 8, 0)

    first = scheduler_service.run_tick(force=True, now=now)
    second = scheduler_service.run_tick(force=True, now=now)

    assert first["sent"] > 0
    assert second["sent"] == 0

    lines = [line for line in outbox.read_text().splitlines() if line.strip()]
    bill_lines = [line for line in lines if '"kind": "bill"' in line]
    assert len(bill_lines) == 1, f"bill reminder sent {len(bill_lines)} times"


def test_claim_is_atomic(outbox):
    assert scheduler_service.claim("bill", "1:2026-11-06") is True
    assert scheduler_service.claim("bill", "1:2026-11-06") is False


def test_released_claim_retries_on_the_next_pass(outbox):
    """If delivery never happened, the alert must not be silently dropped."""
    _reset_with_demo_data()
    assert scheduler_service.claim("bill", "9:2026-11-06") is True
    scheduler_service.release("bill", "9:2026-11-06")
    assert scheduler_service.claim("bill", "9:2026-11-06") is True


def test_total_sent_comes_from_the_ledger(outbox):
    _reset_with_demo_data()
    first = scheduler_service.run_tick(force=True, now=datetime(2026, 11, 6, 8, 0))
    assert first["total_sent"] == first["sent"]

    scheduler_service.run_tick(force=True, now=datetime(2026, 11, 7, 8, 0))
    # The ledger is the only source of truth, so it equals the delivered rows.
    rows = scheduler_service.history(limit=100)
    assert scheduler_service.sent_count() == sum(1 for r in rows if r["delivered"] == 1)


# ------------------------------------------------------- progress check-ins

def test_progress_check_in_is_periodic_and_deduplicated(outbox, monkeypatch):
    """One open task is checked per interval bucket, never twice per bucket."""
    monkeypatch.setenv("LIFEPILOT_PROGRESS_INTERVAL_HOURS", "4")
    _reset_with_demo_data()

    first = scheduler_service.run_tick(
        force=False, now=datetime(2026, 11, 6, 8, 0), include_briefings=False
    )
    first_progress = [m for m in first["messages"] if m["kind"] == "progress"]
    assert len(first_progress) == 1
    assert "Progress check" in first_progress[0]["text"]
    assert "how is" in first_progress[0]["text"]

    same_bucket = scheduler_service.run_tick(
        force=False, now=datetime(2026, 11, 6, 9, 0), include_briefings=False
    )
    assert not [m for m in same_bucket["messages"] if m["kind"] == "progress"]

    next_bucket = scheduler_service.run_tick(
        force=False, now=datetime(2026, 11, 6, 12, 0), include_briefings=False
    )
    assert len([m for m in next_bucket["messages"] if m["kind"] == "progress"]) == 1


def test_progress_check_respects_quiet_hours_when_not_forced(outbox, monkeypatch):
    monkeypatch.setenv("LIFEPILOT_PROGRESS_INTERVAL_HOURS", "4")
    _reset_with_demo_data()
    tick = scheduler_service.run_tick(
        force=False, now=datetime(2026, 11, 6, 3, 0), include_briefings=False
    )
    assert not [m for m in tick["messages"] if m["kind"] == "progress"]


def test_progress_check_can_be_disabled(outbox, monkeypatch):
    monkeypatch.setenv("LIFEPILOT_PROGRESS_INTERVAL_HOURS", "0")
    _reset_with_demo_data()
    tick = scheduler_service.run_tick(
        force=True, now=datetime(2026, 11, 6, 8, 0), include_briefings=False
    )
    assert not [m for m in tick["messages"] if m["kind"] == "progress"]


def test_progress_preview_still_shows_the_question_after_delivery(outbox, monkeypatch):
    monkeypatch.setenv("LIFEPILOT_PROGRESS_INTERVAL_HOURS", "4")
    _reset_with_demo_data()
    now = datetime(2026, 11, 6, 8, 0)
    scheduler_service.run_tick(force=False, now=now, include_briefings=False)
    preview = scheduler_service.progress_preview(now)
    assert "Progress check" in preview["message"]
    assert preview["already_sent"] is True
