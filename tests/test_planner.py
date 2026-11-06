"""Tests for the Planner agent and the planner service."""

from __future__ import annotations

from datetime import date, timedelta

from backend.agents import planner_agent
from backend.services import planner_service, task_service

SAME_DAY = str(date.today() + timedelta(days=3))
LATER = str(date.today() + timedelta(days=10))


def _seed_conflicting_tasks() -> None:
    """Three tasks on one day, one later — triggers a conflict."""
    task_service.create_task({"title": "Biology notes", "deadline": SAME_DAY, "priority": 1,
                              "estimated_minutes": 45}, approved=True)
    task_service.create_task({"title": "Lab report", "deadline": SAME_DAY, "priority": 1,
                              "estimated_minutes": 60}, approved=True)
    task_service.create_task({"title": "Pay rent", "deadline": SAME_DAY, "priority": 2,
                              "estimated_minutes": 10}, approved=True)
    task_service.create_task({"title": "Walk", "deadline": LATER, "priority": 3,
                              "estimated_minutes": 30}, approved=True)


# ---------------------------------------------------------------------------
# Ranking and conflicts
# ---------------------------------------------------------------------------


def test_ranks_by_deadline_then_priority_then_effort():
    _seed_conflicting_tasks()
    ranked = planner_service.rank_tasks()
    deadlines = [t["deadline"] for t in ranked]
    assert deadlines == sorted(deadlines)

    same_day = [t for t in ranked if t["deadline"] == SAME_DAY]
    assert [t["priority"] for t in same_day] == sorted(t["priority"] for t in same_day)


def test_detects_conflicting_deadlines():
    _seed_conflicting_tasks()
    conflicts = planner_service.detect_conflicts()
    assert len(conflicts) == 1
    assert conflicts[0]["deadline"] == SAME_DAY
    assert conflicts[0]["count"] == 3
    assert conflicts[0]["minutes"] == 115


def test_no_conflict_when_deadlines_differ():
    task_service.create_task({"title": "A", "deadline": SAME_DAY}, approved=True)
    task_service.create_task({"title": "B", "deadline": LATER}, approved=True)
    assert planner_service.detect_conflicts() == []


# ---------------------------------------------------------------------------
# Daily plan
# ---------------------------------------------------------------------------


def test_daily_plan_caps_at_three_priorities():
    for index in range(6):
        task_service.create_task({"title": f"Task {index}", "deadline": SAME_DAY}, approved=True)
    plan = planner_service.build({})
    assert len(plan["top_priorities"]) == 3
    assert plan["total_open"] == 6


def test_daily_plan_suggests_postponements_when_overbooked():
    _seed_conflicting_tasks()
    plan = planner_service.build({})
    assert plan["conflicts"]
    assert plan["suggested_postponements"], "an overbooked day should suggest what to drop"


def test_plan_is_not_saved_without_approval():
    task_service.create_task({"title": "A", "deadline": SAME_DAY}, approved=True)
    draft = planner_service.save({}, approved=False)
    assert draft["needs_approval"] is True
    assert draft["plan_id"] is None

    saved = planner_service.save({}, approved=True)
    assert saved["plan_id"] is not None
    assert saved["needs_approval"] is False


def test_planner_agent_never_saves_on_propose():
    _seed_conflicting_tasks()
    proposal = planner_agent.propose_day()
    assert proposal.requires_confirmation is True
    assert proposal.payload["top_priorities"], "proposal should carry the plan"
    assert planner_service.save({}, approved=False)["plan_id"] is None


# ---------------------------------------------------------------------------
# Study plan
# ---------------------------------------------------------------------------


def test_study_plan_splits_hours_across_days():
    exam = str(date.today() + timedelta(days=10))
    plan = planner_service.study_plan(exam, 20, "Biology")
    assert plan["days_left"] == 10
    assert plan["hours_per_day"] == 2.0
    assert plan["subject"] == "Biology"


def test_study_plan_rejects_bad_and_past_dates():
    assert "error" in planner_service.study_plan("not-a-date", 5)
    past = str(date.today() - timedelta(days=2))
    assert "error" in planner_service.study_plan(past, 5)


def test_planner_agent_study_plan_proposal():
    exam = str(date.today() + timedelta(days=5))
    proposal = planner_agent.propose_study_plan(exam, 10, "Algebra")
    assert proposal.kind == "study_plan"
    assert proposal.requires_confirmation is True
    assert "Algebra" in planner_agent.respond_study(proposal)
