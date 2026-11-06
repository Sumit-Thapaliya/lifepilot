"""Typed domain models for LifePilot.

These dataclasses describe the shape of the data that moves between the
services, the agents, and the chat room. They are intentionally dependency
free so they can be imported anywhere without pulling in FastAPI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

# Recognised task categories. Keep in sync with schemas.Category.
Category = Literal["study", "personal", "bill", "health", "household", "work"]
TaskStatus = Literal["pending", "done", "postponed"]

CATEGORIES: tuple[str, ...] = (
    "study",
    "personal",
    "bill",
    "health",
    "household",
    "work",
)


@dataclass
class Task:
    """A single thing the user has to do."""

    id: Optional[int] = None
    title: str = ""
    deadline: Optional[str] = None          # ISO date (YYYY-MM-DD) when known
    category: str = "personal"
    priority: int = 3                       # 1 = highest, 5 = lowest
    notes: str = ""
    suggested_time: Optional[str] = None    # "20:30" — when it should happen
    context: str = ""                       # why, in the model's own words
    estimated_minutes: int = 30
    status: str = "pending"
    postponed_to: Optional[str] = None
    approved: bool = True
    created_at: Optional[str] = None

    @property
    def is_open(self) -> bool:
        return self.status == "pending"


@dataclass
class Bill:
    """A recurring bill such as rent, internet, or electricity."""

    id: Optional[int] = None
    name: str = ""
    amount: float = 0.0
    due_date: Optional[str] = None          # ISO date of the next due date
    recurrence: str = "monthly"             # monthly | weekly | yearly | once
    approved: bool = True


@dataclass
class Reminder:
    """A scheduled nudge shown in the morning briefing or evening review."""

    id: Optional[int] = None
    message: str = ""
    remind_at: Optional[str] = None
    kind: str = "general"                   # general | bill | morning | evening
    sent: bool = False
    approved: bool = False


@dataclass
class DailyPlan:
    """A saved plan for one day, capped at three priorities."""

    id: Optional[int] = None
    plan_date: Optional[str] = None
    top_priorities: list[Task] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    approved: bool = False
    created_at: Optional[str] = None


@dataclass
class MemoryEntry:
    """One stored user preference, e.g. wake_up_time = 07:00."""

    key: str = ""
    value: str = ""


# Preference keys the agents are allowed to read and write.
MEMORY_KEYS: tuple[str, ...] = (
    "wake_up_time",
    "reminder_time",
    "study_subjects",
    "bill_names",
    "timezone",
    "name",
)


@dataclass
class Proposal:
    """Something an agent has understood but not yet saved.

    Every agent returns one of these before touching stored data, so the chat
    reply can honestly say "I have not saved anything yet".
    """

    kind: str                               # task | bill | plan | reminder
    summary: str
    payload: dict = field(default_factory=dict)
    requires_confirmation: bool = True
