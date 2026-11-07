"""Capture Agent.

Role: read what the user sends — text, links, photos, voice-note transcripts —
and turn it into a structured task, bill, or note.

Contract: it ALWAYS shows what it understood and asks before saving. Nothing
reaches the database until the user answers yes.
"""

from __future__ import annotations

import re
from typing import Optional

from ..models import Proposal
from ..services import task_service, understanding_service

NAME = "Capture"

CATEGORIES = ("study", "personal", "bill", "health", "household", "work")

_URL = re.compile(r"https?://\S+")

# Chat words that mean "yes, save it".
AFFIRMATIVES = {"yes", "y", "yeah", "yep", "save", "save it", "confirm", "ok", "okay", "sure", "do it"}
NEGATIVES = {"no", "n", "nope", "cancel", "discard", "don't", "dont", "stop"}


def _clean(message: str) -> str:
    """Drop a trailing URL so it does not pollute the task title."""
    return _URL.sub("", message).strip()


def is_affirmative(message: str) -> bool:
    return message.strip().lower().rstrip(".!") in AFFIRMATIVES


def is_negative(message: str) -> bool:
    return message.strip().lower().rstrip(".!") in NEGATIVES


def propose(message: str, source: str = "text") -> Proposal:
    """Understand one message and return a proposal. Never writes to storage.

    Understanding is delegated to ``understanding_service``: a language model
    when one is configured, the keyword parser otherwise. Either way the result
    is an unconfirmed Proposal — the model never touches the database.
    """
    text = _clean(message)
    result = understanding_service.understand(text)
    parsed = result["parsed"]

    bits = [
        f'"{parsed["title"]}"',
        parsed["category"],
        f'priority {parsed["priority"]}',
        f'due {parsed["deadline"]}' if parsed["deadline"] else "no date",
    ]
    if parsed.get("suggested_time"):
        bits.append(f'around {parsed["suggested_time"]}')
    bits.append(f'about {parsed["estimated_minutes"]} min')

    summary = " — ".join([bits[0], ", ".join(bits[1:])])
    if parsed.get("context"):
        summary += f'\nWhy: {parsed["context"]}'

    return Proposal(
        kind="task",
        summary=summary,
        payload={**parsed, "source": source, "engine": result["engine"]},
        requires_confirmation=True,
    )


def respond(proposal: Proposal) -> str:
    """The short chat reply shown for a proposal."""
    return (
        f"Capture — I understood {proposal.summary}.\n"
        "Nothing is saved yet. Reply 'yes' to save it or 'no' to discard."
    )


def confirm(proposal: Proposal, approved: bool = True) -> dict:
    """Save the proposal when approved; otherwise report that nothing changed."""
    if not approved:
        return {
            "agent": NAME,
            "saved": None,
            "reply": "Discarded. Nothing was saved.",
        }

    payload = {k: v for k, v in proposal.payload.items() if k != "source"}
    saved = task_service.create_task(payload, approved=True)
    return {
        "agent": NAME,
        "saved": saved,
        "reply": (
            f'Saved task #{saved["id"]}: "{saved["title"]}" '
            f'({saved["category"]}, due {saved["deadline"] or "no date"}).'
        ),
    }


def handle(message: str, pending: Optional[Proposal] = None) -> dict:
    """One-turn handler used by the chat router.

    If ``pending`` is a proposal waiting for an answer, a yes/no resolves it.
    Otherwise a new proposal is created.
    """
    if pending is not None:
        if is_affirmative(message):
            return confirm(pending, approved=True)
        if is_negative(message):
            return confirm(pending, approved=False)
        return {
            "agent": NAME,
            "saved": None,
            "reply": "I still have an unsaved proposal. Reply 'yes' to save it or 'no' to discard.",
            "pending": pending,
        }

    proposal = propose(message)
    return {
        "agent": NAME,
        "saved": None,
        "requires_confirmation": True,
        "pending": proposal,
        "reply": respond(proposal),
    }


def handle_photo(result: dict) -> dict:
    """Turn a photo OCR result into a proposal the user can approve."""
    proposals = result.get("proposals") or []
    if not proposals:
        return {"agent": NAME, "reply": result.get("reply", "I could not read that photo.")}

    lines = "\n".join(
        f'{i}. {p["title"]} ({p["category"]}, due {p["deadline"] or "no date"})'
        for i, p in enumerate(proposals, 1)
    )
    engine = result.get("engine", "rules")
    source = "the language model" if engine.startswith("model") else "local OCR rules"
    return {
        "agent": NAME,
        "requires_confirmation": True,
        "pending_photo": proposals,
        "reply": (
            f"Capture found {len(proposals)} task(s) from the photo with {source}:\n{lines}\n"
            "Nothing is saved yet. Reply 'yes' to save them all or 'no' to discard."
        ),
    }


def save_photo_proposals(proposals: list[dict]) -> dict:
    """Save every OCR proposal after the user approves."""
    saved = [task_service.create_task({**p}, approved=True) for p in proposals]
    return {
        "agent": NAME,
        "saved": saved,
        "reply": f"Saved {len(saved)} task(s) from the photo.",
    }
