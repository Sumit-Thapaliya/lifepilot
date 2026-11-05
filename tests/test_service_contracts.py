from backend.services.task_service import parse_task_text
from backend.services.planner_service import build
from backend.services.bill_service import create_bill, list_bills
from backend.services.reminder_service import morning_briefing, evening_review


def test_natural_language_task_extracts_supported_fields() -> None:
    task = parse_task_text("urgent study task: revise algebra tomorrow")
    assert task["category"] == "study"
    assert task["priority"] == 1
    assert task["deadline"] is not None


def test_planner_caps_priorities_and_reports_conflict() -> None:
    result = build({"exam_date": None})
    assert len(result["top_priorities"]) <= 3
    assert "conflicts" in result


def test_bill_and_reminder_service_contracts() -> None:
    bill = create_bill({"name": "Test LifePilot Bill", "amount": 10, "due_date": "2099-01-01"})
    assert bill["name"] == "Test LifePilot Bill"
    assert any(row["id"] == bill["id"] for row in list_bills())
    assert "type" in morning_briefing()
    assert "type" in evening_review()
