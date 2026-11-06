"""Tests for the dynamic understanding layer.

Two promises are tested here:

1. With a language model configured, the model's reading is used — so
   "read a book before bed" can become an evening task.
2. Whatever the model says, this layer clamps it. A model that returns
   nonsense can produce a blank task, never a corrupt row.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services import llm_service, understanding_service


@pytest.fixture
def fake_model(monkeypatch):
    """Pretend a model is configured and let each test choose its answer."""
    holder = {"answer": None, "calls": 0}

    monkeypatch.setattr(llm_service, "available", lambda: True)
    monkeypatch.setattr(llm_service, "model_name", lambda: "test-model")

    def fake_complete_json(system, user):
        holder["calls"] += 1
        holder["user"] = user
        return holder["answer"]

    monkeypatch.setattr(llm_service, "complete_json", fake_complete_json)
    return holder


def test_model_can_infer_a_time_of_day(fake_model):
    """The whole point: 'before bed' is an evening task, not a rule."""
    fake_model["answer"] = {
        "title": "Read a book",
        "category": "personal",
        "priority": 3,
        "deadline": None,
        "suggested_time": "20:30",
        "estimated_minutes": 20,
        "context": "Reading before bed is a bedtime activity.",
    }

    result = understanding_service.understand("read a book before bed")
    parsed = result["parsed"]

    assert parsed["title"] == "Read a book"
    assert parsed["suggested_time"] == "20:30"
    assert "bedtime" in parsed["context"]
    assert result["engine"].startswith("model")


def test_the_model_receives_today_and_preferences(fake_model):
    fake_model["answer"] = {"title": "Call grandma", "category": "personal"}
    understanding_service.understand("call grandma on sunday")
    prompt = fake_model["user"]
    assert date.today().isoformat() in prompt
    assert "Sentence:" in prompt


def test_a_lying_model_cannot_corrupt_the_task(fake_model):
    fake_model["answer"] = {
        "title": "Buy milk",
        "category": "banana",
        "priority": 99,
        "deadline": "1999-01-01",
        "suggested_time": "99:99",
        "estimated_minutes": -5,
    }
    parsed = understanding_service.understand("buy milk")["parsed"]

    assert parsed["category"] == "personal"          # invalid -> fallback
    assert parsed["priority"] == 3                    # out of range -> fallback
    assert parsed["deadline"] is None                 # in the past -> dropped
    assert parsed["suggested_time"] is None           # impossible time -> dropped
    assert parsed["estimated_minutes"] == 20          # nonsense -> fallback


def test_a_future_deadline_is_kept(fake_model):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    fake_model["answer"] = {"title": "Football", "deadline": tomorrow}
    assert understanding_service.understand("football tomorrow")["parsed"]["deadline"] == tomorrow


@pytest.mark.parametrize(
    "raw,expected",
    [("8pm", "20:00"), ("8:30 pm", "20:30"), ("20.30", "20:30"), ("07:00", "07:00"), ("nonsense", None)],
)
def test_time_coercion(raw, expected):
    assert understanding_service._coerce_time(raw) == expected


def test_without_a_model_it_falls_back_to_rules(fake_model):
    fake_model["answer"] = None  # the model failed
    result = understanding_service.understand("pay electricity bill by friday")
    assert result["engine"].startswith("rules")
    assert result["parsed"]["category"] == "bill"


def test_an_empty_title_means_not_a_task(fake_model):
    fake_model["answer"] = {"title": "", "category": "personal"}
    result = understanding_service.understand("I feel sad today")
    assert result.get("not_a_task") is True


def test_status_reports_the_real_mode(monkeypatch):
    monkeypatch.setattr(llm_service, "available", lambda: False)
    assert understanding_service.status()["mode"] == "rules"
    monkeypatch.setattr(llm_service, "available", lambda: True)
    assert understanding_service.status()["mode"] == "model"


# ------------------------------------------------------------- providers

def test_each_free_provider_is_configured_with_one_variable(monkeypatch):
    """One env var must be enough: the base URL and model come from a preset."""
    for name in ("groq", "gemini", "openrouter", "ollama"):
        monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", name)
        for var in ("LIFEPILOT_LLM_MODEL", "LIFEPILOT_LLM_BASE_URL", "LIFEPILOT_LLM_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        assert llm_service.base_url().startswith("http"), name
        assert llm_service.model_name(), name


def test_ollama_needs_no_key(monkeypatch):
    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("LIFEPILOT_LLM_API_KEY", raising=False)
    assert llm_service.available() is True


def test_a_hosted_provider_without_a_key_stays_off(monkeypatch):
    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "groq")
    for var in ("LIFEPILOT_LLM_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert llm_service.available() is False


def test_provider_conventional_env_var_is_accepted(monkeypatch):
    """GROQ_API_KEY works, not just our own variable name."""
    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "groq")
    monkeypatch.delenv("LIFEPILOT_LLM_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert llm_service.available() is True
    assert llm_service.api_key() == "gsk_test"


# ------------------------------------------------------------- .env file

def test_a_key_in_the_env_file_is_picked_up(tmp_path, monkeypatch):
    """The documented setup must actually work: key in .env, not exported."""
    from backend import env_loader

    env_file = tmp_path / ".env"
    env_file.write_text(
        "LIFEPILOT_LLM_PROVIDER=groq\nLIFEPILOT_LLM_API_KEY=gsk_from_file\n",
        encoding="utf-8",
    )
    for var in ("LIFEPILOT_LLM_PROVIDER", "LIFEPILOT_LLM_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    assert env_loader.load_env(env_file) is True
    assert llm_service.provider() == "groq"
    assert llm_service.api_key() == "gsk_from_file"
    assert llm_service.available() is True


def test_a_missing_env_file_is_not_an_error(tmp_path):
    from backend import env_loader

    assert env_loader.load_env(tmp_path / "nope.env") is False


def test_an_exported_variable_beats_the_file(tmp_path, monkeypatch):
    """A one-off override in the shell must win over the file."""
    from backend import env_loader

    env_file = tmp_path / ".env"
    env_file.write_text("LIFEPILOT_LLM_PROVIDER=groq\n", encoding="utf-8")
    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "gemini")

    env_loader.load_env(env_file)
    assert llm_service.provider() == "gemini"


# ------------------------------------------------------- empty .env fields

def test_every_optional_setting_can_be_left_blank(monkeypatch):
    """Blank lines in .env must never break the app — they mean 'use default'."""
    from backend.services import deliver_service, scheduler_service, ticker_service

    for blank in (
        "LIFEPILOT_LLM_MODEL",
        "LIFEPILOT_LLM_BASE_URL",
        "LIFEPILOT_DISCORD_WEBHOOK",
        "LIFEPILOT_SLACK_WEBHOOK",
        "LIFEPILOT_SWITCH_WEBHOOK",
        "LIFEPILOT_TICK_INTERVAL",
        "LIFEPILOT_TASK_WINDOW",
        "LIFEPILOT_BILL_WINDOW",
        "LIFEPILOT_DB",
        "TESSERACT_CMD",
    ):
        monkeypatch.setenv(blank, "")

    assert deliver_service.configured_channel() is None   # no webhook, no attempt
    assert deliver_service.webhook_url() is None
    assert ticker_service.interval_seconds() == 60        # falls back, no crash
    assert scheduler_service.task_window_days() == 1
    assert scheduler_service.bill_window_days() == 3


def test_an_empty_timezone_does_not_become_a_blank_string(monkeypatch):
    """A blank value must fall back, not be stored as ''."""
    monkeypatch.setenv("LIFEPILOT_TIMEZONE", "")
    from backend.services import memory_service

    # A blank line means "not configured", so the fallback is used — never ''.
    assert memory_service.DEFAULTS["timezone"] == "UTC"
