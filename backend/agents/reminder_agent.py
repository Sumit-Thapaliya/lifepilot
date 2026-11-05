"""Reminder message builders; they never send or mutate by themselves."""

def morning_briefing(tasks: list[dict], bills: list[dict], weather: str = "Mock weather: clear") -> dict:
    return {"type": "morning_briefing", "message": f"Good morning. Top tasks: {', '.join(t.get('title', 'Untitled') for t in tasks[:3]) or 'none'}. Bills to watch: {len([b for b in bills if b.get('due_date')])}. {weather}", "sent": False, "action": "awaiting_schedule"}

def bill_due_reminder(bill: dict, days_before: int = 3, approved: bool = False) -> dict:
    result = {"type": "bill_due_reminder", "bill": bill, "days_before": days_before, "requires_confirmation": not approved, "sent": bool(approved)}
    result["response"] = "Action: bill reminder sent." if approved else "Proposed a bill reminder; reply ‘confirm’ before sending."
    return result

def evening_review(completed: list[dict], postponed: list[dict], tomorrow: list[dict]) -> dict:
    return {"type": "evening_review", "completed": completed, "postponed": postponed, "tomorrow_top_three": tomorrow[:3], "sent": False, "action": "awaiting_schedule", "message": f"Evening review: {len(completed)} completed, {len(postponed)} postponed. Tomorrow’s top three: {', '.join(t.get('title', 'Untitled') for t in tomorrow[:3]) or 'none'}."}

def approve_reschedule(approved: bool) -> dict:
    return {"action": "reschedule" if approved else "no_action", "approved": bool(approved), "response": "Action: reminder rescheduled." if approved else "Action: no reminder change made."}
