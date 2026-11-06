"""LifePilot FastAPI application.

Route handlers only validate input and delegate to the services and agents.
All business logic lives in ``backend/services`` and ``backend/agents``.

Run the API:      uvicorn backend.main:app --reload
Run the demo CLI: python -m backend.main --demo
Run the clock:    python -m backend.main --watch
"""

from __future__ import annotations

import argparse
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import database, schemas
from .agents import capture_agent
from .agents.router import route
from .models import Proposal
from .services import (
    bill_service,
    memory_service,
    photo_service,
    planner_service,
    reminder_service,
    scheduler_service,
    task_service,
    ticker_service,
    understanding_service,
)
from .ui import render_ui


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.init_db()
    # The clock starts with the app. One command is now enough to be reminded.
    ticker_service.start()
    yield
    await ticker_service.stop()


app = FastAPI(
    title="LifePilot",
    version="1.0.0",
    description="A personal life operating system that runs inside a Switch chat room.",
    lifespan=lifespan,
)

# The UI is same-origin when opened directly at http://host:8000/, but it is
# also rendered inside sandboxed preview iframes, where the page gets an opaque
# origin ("null"). Browsers still send a CORS preflight for those requests, so
# we allow them explicitly. Data stays local; this is not a public API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https?://.*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health, interface, reset
# ---------------------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    """Liveness, the understanding engine, and whether the reminder clock runs."""
    return {
        "status": "ok",
        "service": "lifepilot",
        "understanding": understanding_service.status(),
        "reminders": ticker_service.status(),
    }


@app.get("/", response_class=HTMLResponse)
def ui() -> str:
    """The live LifePilot interface.

    Served by the backend itself so every control talks to the real API. The
    Switch room remains the primary interface; this page exists so the system
    can be exercised, demoed, and verified without a chat app.
    """
    return render_ui()


@app.post("/reset")
def reset() -> dict:
    """Clear local data. Used by the UI and by repeated demo runs."""
    database.reset_db()
    database.reset_outbox()
    return {"reset": True}


# ---------------------------------------------------------------------------
# Push reminders — the scheduler notices things so the user does not have to
# ---------------------------------------------------------------------------

@app.post("/reminders/tick")
def reminders_tick(force: bool = False) -> dict:
    """Run one scheduler pass.

    Sends anything due (bills near their date, tasks due or overdue, the
    briefings at the configured times) and records each one so it is never sent
    twice. Reads data; never changes a task or bill.
    """
    return scheduler_service.run_tick(force=force)


@app.get("/reminders/history")
def reminders_history(limit: int = 20) -> list[dict]:
    """What the scheduler has actually sent, newest first."""
    return scheduler_service.history(limit=limit)


# ---------------------------------------------------------------------------
# Chat — the Switch room's entry point
# ---------------------------------------------------------------------------

# The Switch room passes its room id as ``sender``; the CLI uses "default".
_PENDING: dict[str, Proposal] = {}


@app.post("/chat", response_model=schemas.ChatResponse)
def chat(payload: schemas.ChatRequest) -> dict:
    """One message from the Switch room. The router picks the agent."""
    sender = payload.sender or "default"
    pending = _PENDING.get(sender)

    result = route(payload.message, pending=pending)

    new_pending = result.get("pending")
    if new_pending is not None:
        _PENDING[sender] = new_pending
    elif not result.get("requires_confirmation"):
        _PENDING.pop(sender, None)

    return result


@app.get("/chat/pending")
def get_pending(sender: str = "default") -> dict:
    """What is waiting for this conversation's yes/no, if anything."""
    pending = _PENDING.get(sender)
    if pending is None:
        return {"pending": None}
    return {
        "pending": {
            "kind": pending.kind,
            "summary": pending.summary,
            "payload": pending.payload,
        }
    }


@app.delete("/chat/pending")
def clear_pending(sender: str = "default") -> dict:
    """Abandon a pending proposal without saving anything."""
    existed = _PENDING.pop(sender, None) is not None
    return {"cleared": existed}


# ---------------------------------------------------------------------------
# Understanding — show your work
# ---------------------------------------------------------------------------

@app.post("/tasks/explain")
def explain_task(payload: schemas.TaskCreate) -> dict:
    """Show exactly what LifePilot understood, and how it got there.

    With a language model configured this returns the model's reading (times,
    context, inferred dates). Without one it returns the deterministic keyword
    parse. The ``engine`` field always says which, so the answer is never
    ambiguous about its own reliability.
    """
    if not payload.text:
        raise HTTPException(422, "Provide natural-language text to explain")
    return understanding_service.understand(payload.text)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@app.post("/tasks/propose")
def propose_task(payload: schemas.TaskCreate) -> dict:
    """Capture a task from natural language. This never saves anything."""
    if not payload.text:
        raise HTTPException(422, "Provide natural-language text to propose a task")
    proposal = capture_agent.propose(payload.text)
    return {
        "requires_confirmation": True,
        "proposal": proposal.payload,
        "reply": capture_agent.respond(proposal),
    }


@app.post("/tasks", status_code=201)
def create_task(payload: schemas.TaskCreate) -> dict:
    """Create a task. Requires approved=true because Capture always confirms."""
    if not payload.approved:
        raise HTTPException(
            400,
            "Capture requires confirmation: send approved=true or use /tasks/propose",
        )
    if not payload.title and not payload.text:
        raise HTTPException(422, "Provide a title or natural-language text")
    return task_service.create_task(payload.model_dump(), approved=True)


@app.get("/tasks")
def list_tasks(status: str | None = None) -> list[dict]:
    return task_service.list_tasks(status=status)


@app.patch("/tasks/{task_id}")
def update_task(task_id: int, payload: schemas.TaskUpdate) -> dict:
    updated = task_service.update_task(task_id, payload.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(404, "Task not found")
    return updated


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int) -> dict:
    task = task_service.complete_task(task_id)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@app.post("/tasks/{task_id}/postpone")
def postpone_task(task_id: int, payload: schemas.PostponeRequest) -> dict:
    task = task_service.postpone_task(task_id, payload.postponed_to)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, approved: bool = False) -> dict:
    """Deleting is a change to stored data, so it needs explicit approval."""
    if not approved:
        raise HTTPException(400, "Deleting a task requires ?approved=true")
    deleted = task_service.delete_task(task_id)
    if not deleted:
        raise HTTPException(404, "Task not found")
    return {"deleted": task_id}


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

@app.post("/plans/daily")
def daily_plan(payload: schemas.PlanRequest | None = None) -> dict:
    """A daily plan with at most three priorities.

    Saving requires ``approved: true``; without it the plan is returned as a
    proposal and nothing is written.
    """
    request = payload.model_dump() if payload else {}
    return planner_service.save(request or {}, approved=bool(request.get("approved")))


@app.post("/plans/study")
def study_plan(payload: schemas.PlanRequest) -> dict:
    """Split available study time across the days before an exam. Never saves."""
    if not payload.exam_date:
        raise HTTPException(422, "Provide an exam date")
    request = payload.model_dump()
    return planner_service.save(request, approved=bool(request.get("approved")))


# ---------------------------------------------------------------------------
# Bills and reminders
# ---------------------------------------------------------------------------

@app.post("/bills", status_code=201)
def create_bill(payload: schemas.BillCreate) -> dict:
    return bill_service.create_bill(payload.model_dump())


@app.get("/bills")
def list_bills() -> list[dict]:
    return bill_service.list_bills()


@app.get("/bills/due")
def bills_due(days: int = 7) -> list[dict]:
    return bill_service.upcoming_bills(within_days=days)


@app.post("/reminders", status_code=201)
def create_reminder(payload: schemas.ReminderCreate) -> dict:
    return reminder_service.create_reminder(payload.model_dump())


@app.get("/reminders")
def list_reminders(kind: str | None = None) -> list[dict]:
    return reminder_service.list_reminders(kind=kind)


@app.post("/briefings/morning")
def morning_briefing() -> dict:
    return reminder_service.morning_briefing()


@app.post("/briefings/evening")
def evening_review() -> dict:
    return reminder_service.evening_review()


# ---------------------------------------------------------------------------
# Photos and memory
# ---------------------------------------------------------------------------

@app.post("/photo/tasks")
async def photo_tasks(file: UploadFile = File(...)) -> dict:
    """Read a photo and propose tasks. Never saves."""
    raw = await file.read()
    return photo_service.extract_tasks(raw)


@app.get("/memory")
def read_memory() -> dict:
    return memory_service.all_values()


@app.put("/memory")
def write_memory(payload: schemas.MemoryWrite) -> dict:
    if payload.key not in memory_service.known_keys():
        raise HTTPException(
            422,
            f"Unknown preference '{payload.key}'. Known keys: "
            + ", ".join(memory_service.known_keys()),
        )
    return memory_service.set_value(payload.key, payload.value)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_watch(interval: int = 60) -> None:
    """Check the clock forever and push reminders when they come due.

    This is what turns LifePilot from answer-only into something that speaks
    first. The API also runs this internally; this command is for running the
    clock as its own process.
    """
    import time

    from .services import deliver_service, scheduler_service

    def say(line: str = "") -> None:
        # flush so the output is visible when piped to a file or `tee`,
        # which is how people actually watch a long-running process.
        print(line, flush=True)

    channel = deliver_service.configured_channel() or "outbox only"
    say("LifePilot watcher started.")
    say(f"  delivery : {channel}")
    say(f"  outbox   : {deliver_service.outbox_path()}")
    say(f"  interval : {interval}s")
    say("  Ctrl-C to stop.\n")

    try:
        while True:
            tick = scheduler_service.run_tick()
            for message in tick["messages"]:
                status = "sent" if message["delivered"] else "FAILED"
                say(f"[{tick['ran_at']}] {status} · {message['kind']}")
                for line in message["text"].splitlines():
                    say(f"    {line}")
                if message.get("error"):
                    say(f"    error: {message['error']}")
                say()
            time.sleep(interval)
    except KeyboardInterrupt:
        say("\nWatcher stopped.")


def run_check() -> int:
    """Diagnose the local setup and print a pass/fail report.

    Written for the moment after someone edits .env and wants to know whether
    it took effect, without reading a stack trace or a JSON health payload.
    """
    import sys
    from pathlib import Path

    from . import database, env_loader
    from .services import deliver_service, llm_service, scheduler_service, ticker_service

    problems = 0

    def line(label: str, value: str, ok: bool | None = None) -> None:
        nonlocal problems
        mark = "" if ok is None else ("  OK  " if ok else " FAIL ")
        if ok is False:
            problems += 1
        print(f"[{mark}] {label:<26} {value}", flush=True)

    print("LifePilot setup check")
    print("=" * 58)

    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    line("Python", version, sys.version_info >= (3, 10))
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    line("Virtual environment", "active" if in_venv else "not active (fine, but recommended)")

    env_path = Path(env_loader.PROJECT_ROOT) / ".env"
    line(".env file", str(env_path) if env_path.exists() else "not found", env_path.exists())

    preset = llm_service.PRESETS.get(llm_service.provider())
    provider_name = llm_service.provider() or "none (using keyword rules)"
    if llm_service.provider() and preset is None:
        line(
            "Language model provider",
            f"'{llm_service.provider()}' is not a known provider",
            False,
        )
        line("Valid providers", ", ".join(sorted(llm_service.PRESETS)))
    else:
        line("Language model provider", provider_name, True if preset else None)

    if preset:
        key = llm_service.api_key()
        if preset[2] and not key:
            line("API key", "missing for this provider", False)
        elif key:
            line("API key", f"{key[:4]}...{key[-4:]} (hidden)", True)
        else:
            line("API key", "not needed (local model)", True)
        line("Model", llm_service.model_name())
        line("Endpoint", llm_service.base_url())
    line(
        "Understanding engine",
        "MODEL - key found" if llm_service.available() else "RULES - no key, works offline",
        True,
    )

    # Offer a live test. It costs one request, so it is opt-in.
    if llm_service.available():
        try:
            answer = input("Send one test request to the model? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Not an interactive terminal (piped output, CI, redirected stdin).
            # Skip the prompt instead of crashing.
            print()
            answer = ""
            line("Live model test", "skipped (no keyboard input)")
        if answer == "y":
            from .services import understanding_service

            result = understanding_service.understand("read a book before bed")
            engine = result["engine"]
            if engine.startswith("model"):
                parsed = result["parsed"]
                line("Live model test", "answered", True)
                line("Sample parse", f'{parsed["title"]} at {parsed.get("suggested_time") or "no time"}')
            else:
                detail = llm_service.status().get("last_error") or result["engine_note"]
                if "401" in str(detail) or "Unauthorized" in str(detail):
                    detail = "the key was rejected (401). Check it was copied whole."
                elif "404" in str(detail):
                    detail = "the model name was not found. Check LIFEPILOT_LLM_MODEL."
                elif "URLError" in str(detail):
                    detail = "no network route to the provider."
                line("Live model test", str(detail)[:60], False)

    db = database.db_path()
    writable = db.parent.exists() or db.parent.mkdir(parents=True, exist_ok=True) is None
    line("Database", str(db.name), writable)
    line("Reminder clock", f"every {ticker_service.interval_seconds()}s when the app runs")
    line("Task warning window", f"{scheduler_service.task_window_days()} day(s) ahead")
    line("Bill warning window", f"{scheduler_service.bill_window_days()} day(s) ahead")
    line("Reminder delivery", deliver_service.configured_channel() or "outbox.log (no webhook)")

    template = Path(env_loader.PROJECT_ROOT) / "switch" / "lifepilot.template.yaml"
    line("Switch template", "found" if template.exists() else "missing", template.exists())

    print("=" * 58)
    if problems == 0:
        print("Everything looks fine. Start it with:")
        print("    uvicorn backend.main:app --reload")
        print("Then open http://localhost:8000/")
    else:
        print(f"{problems} problem(s) found. See the table in SETUP.md.")
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the LifePilot API, the demo, or the reminder watcher"
    )
    parser.add_argument(
        "--demo", action="store_true", help="create sample data and print the workflow"
    )
    parser.add_argument(
        "--watch", action="store_true", help="poll the clock and push reminders until stopped"
    )
    parser.add_argument(
        "--interval", type=int, default=60, help="seconds between scheduler checks (default 60)"
    )
    parser.add_argument(
        "--check", action="store_true", help="diagnose the local setup and exit"
    )
    args = parser.parse_args()

    if args.check:
        raise SystemExit(run_check())
    if args.demo:
        from .seed import run_demo

        run_demo()  # seed a deterministic day, then print the whole workflow
    elif args.watch:
        run_watch(interval=args.interval)
    else:
        import uvicorn

        uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=False)
