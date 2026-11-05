from backend.agents.reminder_agent import bill_due_reminder, evening_review

def test_bill_reminder_waits_for_approval() -> None:
    result = bill_due_reminder({"name": "Rent", "due_date": "2026-11-10"})
    assert result["sent"] is False
    assert result["requires_confirmation"] is True

def test_evening_review_limits_tomorrow_priorities() -> None:
    result = evening_review([], [], [{"title": str(i)} for i in range(4)])
    assert len(result["tomorrow_top_three"]) == 3
