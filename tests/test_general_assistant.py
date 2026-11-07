"""General questions must get answers, not fake task proposals."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.agents import general_agent, router
from backend.main import app
from backend.services import llm_service


@pytest.mark.parametrize(
    "message",
    [
        "what is LifePilot?",
        "how does approval work?",
        "what's the weather like?",
        "hello",
        "thanks",
        "tell me a joke",
        "I like this dashboard",
        "explain the project",
        "still working on the lab report",
        "almost done with the report",
        "yes",
    ],
)
def test_general_messages_do_not_create_a_task_proposal(message):
    result = router.route(message)
    assert result["agent"] == "Assistant"
    assert not result.get("requires_confirmation", False)
    assert "pending" not in result
    assert "Nothing is saved yet" not in result["reply"]


@pytest.mark.parametrize(
    "message",
    [
        "add a task to buy milk",
        "can you add a task to submit the lab report by Friday?",
        "finish biology notes by Friday",
        "pay electricity bill before Friday, urgent",
        "I need to call the landlord tomorrow",
        "remind me to buy milk",
        "track a bill — internet, 1200, due on the 15th, monthly",
    ],
)
def test_actionable_messages_still_reach_capture(message):
    result = router.route(message)
    assert result["agent"] == "Capture"
    assert result.get("requires_confirmation") is True
    assert result.get("pending") is not None


def test_specific_questions_keep_their_product_routes():
    assert router.route("what should I do?")["agent"] == "Planner"
    assert router.route("what bills are due?")["agent"] == "Reminder"
    assert router.route("how did today go?")["agent"] == "Reminder"


def test_capabilities_answer_explains_the_boundary():
    reply = general_agent.answer("what can you do?")["reply"]
    assert "tasks" in reply.lower()
    assert "only ask to save" in reply.lower()
    assert "actionable task" in reply.lower()


def test_progress_question_mentions_the_configured_cadence(monkeypatch):
    monkeypatch.setenv("LIFEPILOT_PROGRESS_INTERVAL_HOURS", "3")
    reply = general_agent.answer("do you remind me about progress?")["reply"]
    assert "progress check" in reply.lower()
    assert "every 3 hours" in reply


def test_status_update_is_acknowledged_without_writing():
    reply = router.route("still working on the biology notes")["reply"]
    assert "have not changed" in reply.lower()


def test_unknown_general_question_can_use_a_configured_model(monkeypatch):
    monkeypatch.setattr(llm_service, "available", lambda: True)

    def fake_complete(system, user, json_mode=False):
        assert json_mode is False
        return "Quantum tunnelling is a small particle effect. LifePilot stays local."

    monkeypatch.setattr(llm_service, "complete", fake_complete)
    result = general_agent.answer("Explain quantum tunnelling simply")
    assert result["payload"]["engine"] == "model"
    assert "LifePilot stays local" in result["reply"]


def test_chat_api_leaves_no_pending_proposal_for_a_general_question():
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message": "what is LifePilot?", "sender": "general-question-api"},
        )
        assert response.status_code == 200
        assert response.json()["agent"] == "Assistant"
        assert response.json()["requires_confirmation"] is False
        pending = client.get(
            "/chat/pending", params={"sender": "general-question-api"}
        ).json()
        assert pending["pending"] is None
