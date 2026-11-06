"""Sample data used by the demo CLI and the tests.

Keeping this in one place means the demo transcript, the tests, and the
screenshots all tell the same story.
"""

from __future__ import annotations

from datetime import date, timedelta

from .agents import capture_agent, planner_agent, reminder_agent
from .services import (
    bill_service,
    memory_service,
    reminder_service,
    scheduler_service,
    task_service,
)


def _relative(days: int) -> str:
    return str(date.today() + timedelta(days=days))


DEMO_TASKS: list[dict] = [
    {"title": "Finish biology notes", "category": "study", "priority": 1,
     "deadline": _relative(0), "estimated_minutes": 45, "notes": "Chapters 4-5, exam next week"},
    {"title": "Pay electricity bill", "category": "bill", "priority": 2,
     "deadline": _relative(0), "estimated_minutes": 10},
    {"title": "30-minute walk", "category": "health", "priority": 3,
     "deadline": _relative(0), "estimated_minutes": 30},
    {"title": "Submit lab report", "category": "study", "priority": 1,
     "deadline": _relative(1), "estimated_minutes": 60},
    {"title": "Call the landlord about water", "category": "household", "priority": 2,
     "deadline": _relative(1), "estimated_minutes": 15},
]

DEMO_MEMORY: dict[str, str] = {
    "name": "Sushil",
    "wake_up_time": "06:30",
    "reminder_time": "20:30",
    "study_subjects": "Biology, Algebra",
    "bill_names": "Rent, Internet, Electricity",
    "timezone": "Asia/Kathmandu",
}


def seed_demo_day() -> dict:
    """Populate a realistic day: tasks, mock bills, one reminder, preferences."""
    created_tasks = [task_service.create_task(task, approved=True) for task in DEMO_TASKS]
    created_bills = bill_service.seed_mock_bills()

    for key, value in DEMO_MEMORY.items():
        memory_service.set_value(key, value)

    reminder_service.create_reminder(
        {
            "message": "Biology exam next week — start revision",
            "remind_at": _relative(2),
            "kind": "study",
            "approved": True,
        }
    )

    return {
        "tasks": created_tasks,
        "bills": created_bills,
        "memory": memory_service.all_values(),
    }


def run_demo() -> None:
    """Create a deterministic sample day and print the whole workflow.

    This is the `python -m backend.main --demo` path. It needs no chat app, no
    network and no API key, and it prints the exact strings the agents would
    send — including the approval step, which is the point of the project.
    """
    from . import database

    database.reset_db()
    data = seed_demo_day()
    tasks = data["tasks"]

    def line(text: str = "") -> None:
        print(text, flush=True)

    def rule(title: str) -> None:
        line()
        line(title)
        line("-" * len(title))

    line("LifePilot demo - no Telegram or Discord required")
    line("=" * 46)

    rule("1. Capture reads a sentence and proposes - it does not save")
    proposal = capture_agent.propose("add a task to finish biology notes by Friday")
    line(capture_agent.respond(proposal))

    rule("2. The user says yes, and only then is anything stored")
    saved = capture_agent.confirm(proposal, approved=True)
    line(saved["reply"])

    rule("3. Planner ranks what is open and caps the day at three priorities")
    plan = planner_agent.propose_day()
    line(planner_agent.respond(plan))

    rule("4. Today's tasks")
    for task in tasks:
        when = f" at {task['suggested_time']}" if task.get("suggested_time") else ""
        line(f"  [{task['priority']}] {task['title']} ({task['category']}, due {task['deadline']}{when})")

    rule("5. Reminder sends the morning briefing")
    line(reminder_service.morning_briefing()["message"])

    rule("6. Reminder sends the evening review")
    line(reminder_service.evening_review()["message"])

    rule("7. A reminder that would change data must ask first")
    postpone = reminder_agent.propose_postpone(tasks[0]["id"], _relative(1))
    line(postpone["reply"])
    line("   (nothing was changed - the user has not answered yet)")

    rule("8. What the scheduler pushes without being asked")
    push = scheduler_service.run_tick(force=True)
    for message in push["messages"][:3]:
        line(f"  -> {message['text'].splitlines()[0]}")
    line(f"  ({push['sent']} message(s) delivered via {push['channel']})")

    line()
    line("Done. Start the API with:  uvicorn backend.main:app --reload")
