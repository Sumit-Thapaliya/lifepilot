"""Reminder Agent.

Role: send the morning briefing, bill due-date reminders, and the evening
review.

Contract: it never changes a task without approval. Rescheduling, deleting, or
postponing anything requires an explicit yes first.
"""

from __future__ import annotations

from ..services import bill_service, reminder_service, task_service

NAME = "Reminder"


# ---------------------------------------------------------------------------
# Scheduled messages — these only read data
# ---------------------------------------------------------------------------


def morning() -> dict:
    """The morning briefing. Reads stored data only."""
    briefing = reminder_service.morning_briefing()
    return {"agent": NAME, "type": "morning", "message": briefing["message"], "data": briefing}


def evening() -> dict:
    """The evening review. Reads stored data only."""
    review = reminder_service.evening_review()
    return {"agent": NAME, "type": "evening", "message": review["message"], "data": review}


def bills(days_before: int = 3) -> dict:
    """Bill due-date reminders. Posts text; changes nothing."""
    result = reminder_service.bill_due_reminders(days_before)
    return {"agent": NAME, "type": "bills", "message": result["message"], "data": result}


# ---------------------------------------------------------------------------
# Actions that change data — every one is approval-gated
# ---------------------------------------------------------------------------


def propose_postpone(task_id: int, postponed_to: str) -> dict:
    """Ask before moving a deadline."""
    task = task_service.get_task(task_id)
    if not task:
        return {"agent": NAME, "reply": f"I can't find task #{task_id}."}
    return {
        "agent": NAME,
        "requires_confirmation": True,
        "pending_action": {"action": "postpone", "task_id": task_id, "postponed_to": postponed_to},
        "reply": (
            f'Move "{task["title"]}" to {postponed_to}? '
            "Reply 'yes' to confirm — I won't change it otherwise."
        ),
    }


def propose_delete(task_id: int) -> dict:
    """Ask before deleting anything."""
    task = task_service.get_task(task_id)
    if not task:
        return {"agent": NAME, "reply": f"I can't find task #{task_id}."}
    return {
        "agent": NAME,
        "requires_confirmation": True,
        "pending_action": {"action": "delete", "task_id": task_id},
        "reply": f'Delete "{task["title"]}"? This cannot be undone. Reply "yes" to confirm.',
    }


def propose_reschedule_reminder(reminder_id: int, remind_at: str) -> dict:
    """Ask before moving a stored reminder."""
    return {
        "agent": NAME,
        "requires_confirmation": True,
        "pending_action": {"action": "reschedule_reminder", "reminder_id": reminder_id,
                           "remind_at": remind_at},
        "reply": f"Move reminder #{reminder_id} to {remind_at}? Reply 'yes' to confirm.",
    }


def execute(action: dict, approved: bool = True) -> dict:
    """Run a previously proposed action only when the user approved it."""
    if not approved:
        return {"agent": NAME, "reply": "Cancelled. Nothing was changed."}

    kind = action.get("action")
    if kind == "postpone":
        updated = task_service.postpone_task(action["task_id"], action["postponed_to"])
        return {
            "agent": NAME,
            "changed": updated,
            "reply": f'Moved "{updated["title"]}" to {action["postponed_to"]}.',
        }
    if kind == "delete":
        result = task_service.delete_task(action["task_id"], approved=True)
        return {"agent": NAME, "changed": result, "reply": f'Deleted task #{result["deleted"]}.'}
    if kind == "reschedule_reminder":
        return {
            "agent": NAME,
            "reply": f"Reminder #{action['reminder_id']} noted for {action['remind_at']}. "
                     "Nothing else was changed.",
        }
    return {"agent": NAME, "reply": "I don't recognise that action, so I changed nothing."}


# ---------------------------------------------------------------------------
# Helpers used by the chat router
# ---------------------------------------------------------------------------


def stats() -> dict:
    """Quick counts the agent can quote in one line."""
    tasks = task_service.list_tasks()
    return {
        "pending": len([t for t in tasks if t["status"] == "pending"]),
        "done": len([t for t in tasks if t["status"] == "done"]),
        "postponed": len([t for t in tasks if t["status"] == "postponed"]),
        "bills_due": len(bill_service.upcoming_bills(within_days=7)),
    }
