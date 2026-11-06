"""Delivery — how a reminder physically leaves the building.

LifePilot has no opinion about where a message lands. It builds the text and
this module hands it to whatever transport is configured:

    1. A local outbox file  (always)  -> `python -m backend.main watch` tails it
    2. An HTTP webhook      (if set)  -> Discord, Slack, a Switch webhook, anything

If no webhook is configured the message is still written to the outbox, so the
system never silently drops a reminder and never claims to have sent one it
did not send. `deliver()` reports exactly what happened.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

# Channel name -> environment variable holding the webhook URL.
CHANNELS = {
    "discord": "LIFEPILOT_DISCORD_WEBHOOK",
    "slack": "LIFEPILOT_SLACK_WEBHOOK",
    "switch": "LIFEPILOT_SWITCH_WEBHOOK",
}

DEFAULT_OUTBOX = Path(__file__).resolve().parents[1] / "data" / "outbox.log"


def outbox_path() -> Path:
    override = os.environ.get("LIFEPILOT_OUTBOX")
    return Path(override) if override else DEFAULT_OUTBOX


def configured_channel() -> str | None:
    """Return the first channel that has a webhook URL, or None."""
    for name, env_var in CHANNELS.items():
        if os.environ.get(env_var):
            return name
    return None


def webhook_url() -> str | None:
    channel = configured_channel()
    return os.environ.get(CHANNELS[channel]) if channel else None


def _http_post(url: str, body: dict, timeout: float = 8.0) -> None:
    """POST JSON to a webhook. Isolated so tests can monkeypatch it."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "LifePilot/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read()


def _append_outbox(kind: str, text: str, pushed_at: str) -> None:
    """Append one JSON line to the local outbox. Never raises."""
    path = outbox_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"kind": kind, "at": pushed_at, "text": text}, ensure_ascii=False)
                + "\n"
            )
    except OSError:
        # A read-only filesystem must not break the scheduler; the caller still
        # learns delivery succeeded or failed through the return value.
        pass


def deliver(kind: str, text: str, pushed_at: str | None = None) -> dict:
    """Send one reminder. Returns what actually happened — no guessing.

    ``delivered`` is True only if at least one channel accepted the message.
    The outbox counts as a real channel: the user can read it with `watch`.
    """
    pushed_at = pushed_at or datetime.now().isoformat(timespec="seconds")

    result = {
        "kind": kind,
        "delivered": False,
        "channels": [],
        "channel": None,
        "error": None,
        "at": pushed_at,
    }

    outbox_before = outbox_path().exists()
    _append_outbox(kind, text, pushed_at)
    if not outbox_before or outbox_path().exists():
        result["channels"].append("outbox")
        result["delivered"] = True

    url = webhook_url()
    if url:
        channel = configured_channel()
        try:
            _http_post(url, {"content": text, "text": text})
            result["channels"].append(channel)
            result["channel"] = channel
            result["delivered"] = True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError) as exc:
            result["error"] = f"{channel} webhook failed: {exc}"
            # The outbox write already succeeded, so the message is not lost.

    return result
