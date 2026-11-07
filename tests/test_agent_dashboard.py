"""Dashboard tests for the three-agent division-of-work panel."""

from __future__ import annotations

import re

from backend.ui import render_ui

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


def _agent_panel(html: str) -> str:
    start = html.index('id="agents"')
    end = html.index("</section>", start)
    return html[start:end]


def test_dashboard_shows_three_agents_and_division_of_work():
    html = render_ui()
    panel = _agent_panel(html)

    assert 'id="agents"' in html
    assert "Three agents, three jobs" in panel
    assert "Division of work" in panel
    for name in ("Capture Agent", "Planner Agent", "Reminder Agent"):
        assert name in panel
    assert panel.count('class="agent-card ') == 3
    assert panel.count('class="agent-row') == 12, "each agent needs Reads, Decides, Writes, Never"
    for label in ("Reads", "Decides", "Writes", "Never"):
        assert f">{label}<" in panel
    assert "Your approval" in panel
    assert "General questions are handled by the Assistant routing path" in panel
    assert ">Agents</button>" in html
    assert "focusAgents()" in html


def test_agent_panel_has_no_emoji_and_points_to_source_modules():
    html = render_ui()
    panel = _agent_panel(html)

    assert EMOJI.search(panel) is None
    for module in (
        "backend/agents/capture_agent.py",
        "backend/agents/planner_agent.py",
        "backend/agents/reminder_agent.py",
    ):
        assert module in panel
    assert "/tasks/propose" in panel
    assert "/plans/daily" in panel
    assert "/reminders/tick" in panel
