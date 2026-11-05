from backend.agents.planner_agent import create_daily_plan, detect_conflicts

def test_daily_plan_has_three_priorities_and_conflicts() -> None:
    tasks = [{"title": str(i), "deadline": "2026-11-07", "priority": "high"} for i in range(4)]
    result = create_daily_plan(tasks)
    assert len(result["top_priorities"]) == 3
    assert len(detect_conflicts(tasks)) == 1
    assert result["requires_confirmation"] is True
