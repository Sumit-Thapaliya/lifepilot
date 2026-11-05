from backend.services import bill_service, planner_service, reminder_service, task_service


def test_task_creation_requires_confirmation_then_saves():
    preview = task_service.create_task({"text": "urgent study algebra today"}, approved=False)
    assert preview["status"] == "pending_approval"
    saved = task_service.create_task({"text": "urgent study algebra today"}, approved=True)
    assert saved["category"] == "study"
    assert saved["approved"] == 1


def test_daily_plan_caps_priorities_and_flags_approval():
    for i in range(4):
        task_service.create_task({"title": f"Plan task {i}", "priority": i + 1}, approved=True)
    result = planner_service.create_daily_plan(None, approved=False)
    assert len(result["content"]["top_priorities"]) <= 3
    assert result["needs_approval"] is True


def test_bill_and_reminder_briefing_are_local():
    bill = bill_service.create_bill({"name": "Internet", "amount": 25, "due_date": "2099-02-01", "approved": True})
    assert bill["name"] == "Internet"
    briefing = reminder_service.morning_briefing()
    review = reminder_service.evening_review()
    assert briefing["type"] == "morning"
    assert review["type"] == "evening"
