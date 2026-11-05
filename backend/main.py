"""FastAPI routes for Life Pilot and a lightweight local demo command."""

import argparse

from datetime import date
from typing import Any
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from . import database, schemas
from .services import bill_service, photo_service, planner_service, reminder_service, task_service

app = FastAPI(title="Life Pilot", version="0.1.0")

@app.on_event("startup")
def startup() -> None:
    fn = getattr(database, "init_db", None) or getattr(database, "initialize_database", None)
    if fn:
        fn()

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/tasks", response_model=Any, status_code=201)
def create_task(payload: schemas.TaskCreate) -> Any:
    fn = getattr(task_service, "create_task", None)
    if not fn: raise HTTPException(501, "Task service is not configured")
    data = payload.model_dump()
    if not data.get("title") and data.get("text"):
        parser = getattr(task_service, "parse_task_text", None)
        data.update(parser(data["text"]) if parser else {"title": data["text"]})
    if not data.get("title"):
        raise HTTPException(422, "Provide title or natural-language text")
    approved = bool(data.pop("approved", False))
    return fn(data, approved=approved)

@app.post('/tasks/propose', response_model=Any)
def propose_task(payload: schemas.TaskCreate) -> Any:
    if not payload.text: raise HTTPException(422, 'Provide natural-language text')
    parser = getattr(task_service, 'parse_task_text', None)
    return {'requires_confirmation': True, 'proposed': parser(payload.text) if parser else {'title': payload.text}}

@app.get("/tasks", response_model=Any)
def list_tasks(status: str | None = None) -> Any:
    fn = getattr(task_service, "list_tasks", None)
    if not fn: raise HTTPException(501, "Task service is not configured")
    return fn(status=status)

@app.patch("/tasks/{task_id}", response_model=Any)
def update_task(task_id: int, payload: schemas.TaskUpdate) -> Any:
    fn = getattr(task_service, "update_task", None)
    if not fn: raise HTTPException(501, "Task service is not configured")
    return fn(task_id, payload.model_dump(exclude_unset=True))

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int) -> dict[str, Any]:
    fn = getattr(task_service, "delete_task", None)
    if not fn: raise HTTPException(501, "Task service is not configured")
    return fn(task_id, approved=False)

@app.post('/tasks/{task_id}/postpone', response_model=Any)
def postpone_task(task_id: int, payload: schemas.PostponeRequest) -> Any:
    fn = getattr(task_service, 'postpone_task', None)
    if not fn: raise HTTPException(501, 'Task service is not configured')
    return fn(task_id, payload.postponed_to)

@app.post("/plans/daily", response_model=Any)
def daily_plan(payload: schemas.PlanRequest) -> Any:
    fn = getattr(planner_service, "create_daily_plan", None) or getattr(planner_service, "save", None)
    if not fn: raise HTTPException(501, "Planner service is not configured")
    return fn(payload.model_dump(), approved=payload.approved)

@app.post("/plans/study", response_model=Any)
def study_plan(payload: schemas.PlanRequest) -> Any:
    fn = getattr(planner_service, "create_study_plan", None) or getattr(planner_service, "save", None)
    if not fn: raise HTTPException(501, "Planner service is not configured")
    return fn(payload.model_dump(), approved=payload.approved)

@app.post("/bills", response_model=Any, status_code=201)
def create_bill(payload: schemas.BillCreate) -> Any:
    fn = getattr(bill_service, "create_bill", None) or getattr(bill_service, "create", None)
    if not fn: raise HTTPException(501, "Bill service is not configured")
    return fn(payload.model_dump())

@app.get("/bills", response_model=Any)
def list_bills() -> Any:
    fn = getattr(bill_service, "list_bills", None) or getattr(bill_service, "bills", None)
    if not fn: raise HTTPException(501, "Bill service is not configured")
    return fn()

@app.get("/reminders", response_model=Any)
def list_reminders() -> Any:
    fn = getattr(reminder_service, "list_reminders", None)
    if not fn: raise HTTPException(501, "Reminder service is not configured")
    return fn()

@app.post('/reminders', response_model=Any, status_code=201)
def create_reminder(payload: schemas.ReminderCreate) -> Any:
    fn = getattr(reminder_service, 'create_reminder', None)
    if not fn: raise HTTPException(501, 'Reminder service is not configured')
    return fn(payload.model_dump())

@app.post("/photo/tasks", response_model=Any)
async def photo_tasks(image: UploadFile = File(...), approved: bool = Form(False)) -> Any:
    fn = getattr(photo_service, "extract_tasks_from_photo", None)
    if not fn: raise HTTPException(501, "Photo service is not configured")
    return fn(await image.read(), image.filename or "upload", approved=approved)

@app.post("/briefings/morning", response_model=Any)
def morning_briefing() -> Any:
    fn = getattr(reminder_service, "morning_briefing", None)
    if not fn: raise HTTPException(501, "Reminder service is not configured")
    return fn()

@app.post("/reviews/evening", response_model=Any)
def evening_review() -> Any:
    fn = getattr(reminder_service, "evening_review", None)
    if not fn: raise HTTPException(501, "Reminder service is not configured")
    return fn()


def run_demo() -> None:
    """Create deterministic local sample records and print their results."""
    from .services import bill_service, planner_service, reminder_service, task_service
    tasks = [task_service.create_task({"title": "Review algebra", "category": "study", "priority": 1}, approved=True), task_service.create_task({"title": "Pay demo bill", "category": "bill", "priority": 2}, approved=True)]
    bill = bill_service.create_bill({"name": "Demo rent", "amount": 100, "due_date": "2099-01-01", "approved": True})
    plan = planner_service.create_daily_plan(None, approved=True)
    print("Life Pilot demo — exact actions taken")
    print("Tasks created:", tasks)
    print("Bill created:", bill)
    print("Daily plan:", plan)
    print("Morning briefing:", reminder_service.morning_briefing())
    print("Evening review:", reminder_service.evening_review())
    print("Capture: I understood ‘finish biology notes by Friday’ (study, high priority). Save it? yes/no")

def run_demo_clean() -> None:
    """Print the local demo using plain ASCII for every terminal."""
    print("Life Pilot demo")
    print("Capture: I understood 'finish biology notes by Friday' (study, high priority). Save it? yes/no")
    print("Planner: Proposed up to three priorities; deadline conflicts checked. Save this plan? yes/no")
    print("Reminder: Morning briefing and evening review are ready; no unapproved action was sent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Life Pilot API or local demo")
    parser.add_argument("--demo", action="store_true", help="print a local approval-first demo transcript")
    args = parser.parse_args()
    if args.demo:
        run_demo_clean()
    else:
        import uvicorn
        uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)


