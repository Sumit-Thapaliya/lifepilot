"""Pydantic request/response models for the FastAPI layer.

Route handlers only validate input and delegate. All business logic lives in
``backend/services`` and ``backend/agents``.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Category = Literal["study", "personal", "bill", "health", "household", "work"]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    """Either provide a title, or raw text that Capture should parse."""

    title: Optional[str] = None
    text: Optional[str] = Field(None, description="Natural language, e.g. 'pay rent tomorrow'")
    deadline: Optional[str] = None
    category: Category = "personal"
    priority: int = Field(3, ge=1, le=5)
    notes: str = ""
    suggested_time: Optional[str] = Field(
        None, description="HH:MM — when the task should actually happen"
    )
    context: str = Field("", description="Why this was understood this way")
    estimated_minutes: int = Field(30, ge=1)
    approved: bool = False


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    deadline: Optional[str] = None
    category: Optional[Category] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    suggested_time: Optional[str] = None
    context: Optional[str] = None
    estimated_minutes: Optional[int] = None
    status: Optional[Literal["pending", "done", "postponed"]] = None


class PostponeRequest(BaseModel):
    postponed_to: str


class ConfirmRequest(BaseModel):
    """The user's answer to a proposal. Nothing is saved without approved=True."""

    approved: bool = False


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------


class PlanRequest(BaseModel):
    plan_date: Optional[str] = None
    exam_date: Optional[str] = Field(None, description="ISO date for a study plan")
    study_hours: Optional[float] = Field(None, ge=0, description="Total hours available before the exam")
    study_subject: Optional[str] = None
    approved: bool = False


# ---------------------------------------------------------------------------
# Bills and reminders
# ---------------------------------------------------------------------------


class BillCreate(BaseModel):
    name: str
    amount: float = 0
    due_date: Optional[str] = None
    recurrence: str = "monthly"
    approved: bool = True


class ReminderCreate(BaseModel):
    message: str
    remind_at: Optional[str] = None
    kind: str = "general"
    approved: bool = True


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class MemoryWrite(BaseModel):
    key: str
    value: str


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """One message from the Switch room; a router picks the agent."""

    message: str
    sender: Optional[str] = Field(
        None,
        description="Conversation id (Switch room id). Keeps pending proposals separate per room.",
    )


class ChatResponse(BaseModel):
    agent: str
    reply: str
    requires_confirmation: bool = False
    payload: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Compatibility aliases kept for existing tests and imports
# ---------------------------------------------------------------------------

DailyPlanRequest = PlanRequest
StudyPlanRequest = PlanRequest
Approval = ConfirmRequest
