"""Tests for the Switch template.

The template is the artifact a judge actually reads, so it must not drift away
from the code. These tests parse `switch/lifepilot.template.yaml` and check that
every command it tells an agent to run points at an endpoint that exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.yaml_shim import safe_load

TEMPLATE = Path(__file__).resolve().parents[1] / "switch" / "lifepilot.template.yaml"


@pytest.fixture(scope="module")
def template() -> dict:
    return safe_load(TEMPLATE)


def test_template_parses_and_has_the_mandated_shape(template):
    assert template["version"] == 2
    resources = template["resources"]
    assert "lifepilot_room" in resources
    for agent in ("capture_agent", "planner_agent", "reminder_agent"):
        assert agent in resources, f"{agent} missing"
        assert resources[agent]["type"] == "agent"


def test_room_has_three_agents_and_the_user(template):
    room = template["resources"]["lifepilot_room"]
    assert room["type"] == "room"
    assert room["name"] == "lifepilot"
    assert len(room["agents"]) == 3
    assert "{user}" in room["users"]
    assert "kickoff" in room


def test_kickoff_message_is_under_the_limit(template):
    kickoff = template["resources"]["lifepilot_room"]["kickoff"]
    assert len(kickoff) < 2000, "kickoff must stay short enough for chat"


@pytest.mark.parametrize("agent", ["capture_agent", "planner_agent", "reminder_agent"])
def test_every_agent_delegates_to_the_backend(template, agent):
    """Each agent must call the API rather than re-implement the rules."""
    instructions = template["resources"][agent]["instructions"]
    assert "curl" in instructions, f"{agent} does not call the backend"
    assert "localhost:8000" in instructions, f"{agent} has no target for its calls"


@pytest.mark.parametrize("agent", ["capture_agent", "planner_agent", "reminder_agent"])
def test_every_agent_keeps_the_approval_rule(template, agent):
    """The template must still forbid acting without a yes."""
    instructions = template["resources"][agent]["instructions"].lower()
    assert "yes" in instructions
    assert any(word in instructions for word in ("confirm", "approv", "never claim"))


def test_every_endpoint_named_in_the_template_exists(template):
    """No invented endpoints: each URL must be one the app actually serves."""
    from fastapi.testclient import TestClient

    from backend.main import app

    paths = set(app.openapi()["paths"].keys())

    referenced: set[str] = set()
    for name, resource in template["resources"].items():
        instructions = resource.get("instructions") or ""
        for token in instructions.split():
            if "localhost:8000/" not in token:
                continue
            path = token.split("localhost:8000", 1)[1].strip("'\"\\")
            path = path.split("?")[0]
            if path:
                referenced.add(path)

    assert referenced, "the template names no endpoints at all"
    for path in referenced:
        assert path in paths, f"template calls {path}, which the app does not serve"

    # And they really answer, not just appear in the schema.
    with TestClient(app) as client:
        for path in referenced:
            method = "post" if path.startswith(("/chat", "/briefings")) else "get"
            response = getattr(client, method)(path)
            assert response.status_code < 500, f"{method.upper()} {path} returned {response.status_code}"


# ---------------------------------------------------------------- the UI

def test_the_ui_javascript_is_syntactically_valid():
    """A single broken escape in ui.py kills every button on the page.

    This caught two real regressions (`\\n` inside a JS string), so it is a test
    rather than a habit. node --check is a parse check only — nothing runs.
    """
    import subprocess
    import tempfile

    from backend.ui import render_ui

    html = render_ui()
    assert "<script>" in html and "</script>" in html
    js = html.split("<script>")[-1].split("</script>")[0]
    assert js.strip(), "the UI has no JavaScript"

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(js)
        path = handle.name

    result = subprocess.run(
        ["node", "--check", path], capture_output=True, text=True
    )
    assert result.returncode == 0, f"UI JavaScript does not parse:\n{result.stderr}"


def test_the_demo_command_runs(capsys):
    """`python -m backend.main --demo` is in the spec; it must execute."""
    from backend.seed import run_demo

    run_demo()
    out = capsys.readouterr().out
    assert "LifePilot demo" in out
    assert "Nothing is saved yet" in out
    assert "Saved task" in out


def test_the_setup_check_runs_and_hides_the_key(monkeypatch, capsys):
    """`--check` is the first thing a new user runs; it must not leak the key."""
    from backend.main import run_check

    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "groq")
    monkeypatch.setenv("LIFEPILOT_LLM_API_KEY", "gsk_supersecret_value_9999")
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    code = run_check()
    out = capsys.readouterr().out

    assert "gsk_supersecret_value_9999" not in out, "the full key must never be printed"
    assert "gsk_...9999" in out
    assert "groq" in out
    assert code in (0, 1)


def test_the_setup_check_flags_an_unknown_provider(monkeypatch, capsys):
    from backend.main import run_check

    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "grok")
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    code = run_check()
    out = capsys.readouterr().out
    assert "not a known provider" in out
    assert code == 1


def test_the_setup_check_does_not_crash_without_a_keyboard(monkeypatch, capsys):
    """Piped/redirected output must not raise EOFError at the live-test prompt."""
    from backend import main

    monkeypatch.setenv("LIFEPILOT_LLM_PROVIDER", "groq")
    monkeypatch.setenv("LIFEPILOT_LLM_API_KEY", "gsk_pretend_key_1234")

    def no_input(*_args, **_kwargs):
        raise EOFError

    monkeypatch.setattr("builtins.input", no_input)
    code = main.run_check()
    out = capsys.readouterr().out
    assert "skipped (no keyboard input)" in out
    assert "gsk_pretend_key_1234" not in out
    assert isinstance(code, int)


def test_the_template_can_be_read_without_pyyaml():
    """PyYAML cannot install on Python 3.15 (no wheels, no Visual C++).

    The app never imports yaml, but the template tests do, so the fallback has
    to work. This blocks a future edit that imports yaml directly again.
    """
    import importlib.util
    import subprocess
    import sys

    try:
        has_ruamel = importlib.util.find_spec("ruamel.yaml") is not None
    except (ImportError, ModuleNotFoundError):
        has_ruamel = False
    if not has_ruamel:
        pytest.skip("ruamel.yaml not installed; nothing to fall back to")

    code = (
        "import sys\n"
        "sys.modules['yaml'] = None  # simulate PyYAML being unavailable\n"
        "from tests.yaml_shim import safe_load\n"
        "d = safe_load('switch/lifepilot.template.yaml')\n"
        "print(d['version'], len(d['resources']['lifepilot_room']['agents']))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=TEMPLATE.parents[1],
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "2 3"
