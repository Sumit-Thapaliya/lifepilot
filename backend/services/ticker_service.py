"""The ticker — a clock inside the app, so one command is enough.

Before this module existed, reminders only fired if the user remembered to run
`python -m backend.main watch` in a second terminal. A reminder system that
needs you to remember to start it is not a reminder system.

The ticker starts with the API and, every ``interval`` seconds, asks the
scheduler whether anything is due. Everything it sends still goes through
``scheduler_service.run_tick()``, so deduplication and the audit trail are
unchanged — this is only a heartbeat, not new logic.

Turn it off with ``LIFEPILOT_TICK=0`` (the tests do this).
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Optional

STATE = {
    "running": False,
    "interval": 60,
    "started_at": None,
    "last_tick_at": None,
    "last_sent": 0,
    "total_sent": 0,
    "error": None,
}

_task: Optional[asyncio.Task] = None


def enabled() -> bool:
    """The ticker runs by default; set LIFEPILOT_TICK=0 to disable it."""
    return os.environ.get("LIFEPILOT_TICK", "1") not in {"0", "false", "False", "off"}


def interval_seconds() -> int:
    try:
        return max(5, int(os.environ.get("LIFEPILOT_TICK_INTERVAL", 60)))
    except (TypeError, ValueError):
        return 60


def _one_pass() -> None:
    """Run one scheduler pass and record what happened. Never raises."""
    from . import scheduler_service

    try:
        result = scheduler_service.run_tick()
        STATE["last_tick_at"] = result["ran_at"]
        STATE["last_sent"] = result["sent"]
        # Read the total from the ledger, not a counter in memory: a counter
        # drifts the moment anything else writes a delivery (the UI button,
        # another process) and then reports numbers that are simply untrue.
        STATE["total_sent"] = result.get("total_sent", STATE["total_sent"])
        STATE["error"] = None
    except Exception as exc:  # a broken tick must not kill the loop
        STATE["error"] = f"{type(exc).__name__}: {exc}"


async def _loop() -> None:
    STATE["running"] = True
    STATE["started_at"] = datetime.now().isoformat(timespec="seconds")
    STATE["interval"] = interval_seconds()
    while True:
        _one_pass()
        await asyncio.sleep(STATE["interval"])


def start() -> bool:
    """Start the background heartbeat. Safe to call twice."""
    global _task
    if not enabled():
        return False
    if _task is not None and not _task.done():
        return True
    _task = asyncio.create_task(_loop())
    return True


async def stop() -> None:
    """Stop the heartbeat cleanly on shutdown."""
    global _task
    if _task is None:
        return
    _task.cancel()
    try:
        await _task
    except (asyncio.CancelledError, Exception):
        pass
    _task = None
    STATE["running"] = False


def status() -> dict:
    """What the user-facing health check reports."""
    return {
        "enabled": enabled(),
        "running": STATE["running"],
        "interval_seconds": STATE["interval"],
        "started_at": STATE["started_at"],
        "last_tick_at": STATE["last_tick_at"],
        "last_sent": STATE["last_sent"],
        "total_sent": STATE["total_sent"],
        "error": STATE["error"],
        "mode": "automatic — the app checks the clock for you",
    }
