"""Deterministic capture-agent behavior; proposals never save automatically."""

from __future__ import annotations
import re

CATEGORIES = {"study", "personal", "bill", "health", "household", "work"}

def _category(text: str) -> str:
    value = text.lower()
    for category in CATEGORIES:
        if category in value:
            return category
    if any(word in value for word in ("exam", "study", "assignment")):
        return "study"
    if any(word in value for word in ("bill", "rent", "invoice")):
        return "bill"
    return "personal"

def _priority(text: str) -> str:
    value = text.lower()
    if any(word in value for word in ("urgent", "asap", "immediately")):
        return "high"
    if any(word in value for word in ("important", "soon")):
        return "medium"
    return "low"

def extract_capture(text: str) -> dict:
    cleaned = re.sub(r"^(add|create|remember|track)\s+(a\s+)?task\s*[:,-]?\s*(?:to\s+)?", "", text.strip(), flags=re.I)
    match = re.search(r"\s+(?:by|on|due)\s+([^,.;]+)", cleaned, flags=re.I)
    deadline = match.group(1).strip() if match else None
    title = re.split(r"\s+(?:by|on|due)\s+", cleaned, maxsplit=1, flags=re.I)[0].strip(" .") or "Untitled task"
    title = re.sub(r"^to\s+", "", title, flags=re.I)
    proposal = {"title": title, "deadline": deadline, "category": _category(cleaned), "priority": _priority(cleaned), "notes": None, "requires_confirmation": True, "confirmed": False}
    proposal["response"] = f"I understood: {title} | category: {proposal['category']} | priority: {proposal['priority']} | deadline: {deadline or 'none'}. Reply ‘confirm’ to save it."
    return proposal

def confirm_capture(proposal: dict, confirmed: bool) -> dict:
    result = dict(proposal)
    result.update(confirmed=bool(confirmed), action="save_task" if confirmed else "discard_proposal")
    result["response"] = "Action: task approved for saving." if confirmed else "Action: proposal discarded; nothing was saved."
    return result
