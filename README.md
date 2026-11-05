# Life Pilot

Life Pilot is a personal life operating system that turns everyday chat into
an organised, approval-first workflow. A user can send a deadline, bill,
photo, voice-note transcript, equation, or plain-language request; Life Pilot
extracts the useful information, proposes the next action, and waits for the
user to confirm anything that changes stored data or a plan.

## Why it exists

Important tasks are often scattered across chat messages, photos, notes, and
calendar-like reminders. Life Pilot keeps those inputs in one local SQLite
database, creates a focused daily plan, tracks recurring bills, and provides
morning and evening summaries without requiring a paid API.

## Switch architecture

Switch connects one user and three focused agents in a shared Life Pilot room
on Discord or Mattermost. The room is the conversational interface; the local
FastAPI backend is the source of truth. Agents call backend services rather
than putting business logic in chat handlers.

- **Capture** extracts title, deadline, category, priority, effort, and notes
  from natural language or media. It displays the extraction and asks before
  saving.
- **Planner** ranks work by deadline, priority, and effort; proposes up to
  three daily priorities; flags conflicts; and creates approved study plans.
- **Reminder** sends an approved morning briefing, bill due-date reminders,
  and an evening review. It asks before rescheduling or deleting anything.

All agents keep replies short, state the exact action taken, and clearly label
proposals that still need approval.

## Install and run locally

There is no frontend to build or configure. The Switch room is the user
interface and the API is a local Python process. From the project directory:

```powershell
cd lifepilot
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

For a quick local smoke/demo run, use a second terminal while the virtual
environment is active:

```powershell
cd lifepilot
.venv\\Scripts\\Activate.ps1
python -m backend.main --demo
```

The SQLite database lives at `backend/data/lifepilot.db`. Copy `.env.example`
to `.env` when you need to change the database path or timezone. OCR uses the
local Pillow/pytesseract stack; if the Tesseract executable is not installed,
the photo service returns a clear fallback response rather than pretending it
read the image.

## Import the Switch template

Open `switch/lifepilot.template.yaml` in Switch Console's template importer
(or pass it to the Switch `create_room_from_yaml` workflow). Choose the active
Discord or Mattermost bridge, the online agent machine, and the existing agent
names when prompted. The template defines the three agent roles, invites the
configured user, creates the shared room, and posts the kickoff message.
Review the generated room and agent permissions before sending real data.

## Public-repository workflow

The repository is designed to run without secrets or paid services:

1. Clone the repository and create the virtual environment using the commands
   above.
2. Copy `.env.example` to `.env`; never commit the real `.env` or database
   contents containing personal data.
3. Run the API locally and import the Switch template into a development room.
4. Use mock weather/bill data and local OCR for demos; keep production
   connectors out of the public repository.
5. Run tests with `pytest` before opening a pull request. Keep changes to
   backend, template, docs, and tests separated so reviews stay focused.

## Demo transcript

```text
User: add a task - finish the biology notes by Friday, high priority
Capture: I understood: "Finish biology notes"; deadline Friday; category study;
         priority high. Save this task? (yes/no)
User: yes
Capture: Saved task "Finish biology notes" with the Friday deadline.

User: plan my day
Planner: Proposed top 3: biology notes, pay electricity bill, 30-minute walk.
         I found no deadline conflict. Save this plan? (yes/no)
User: yes
Planner: Saved today's plan with those three priorities.

User: track a bill: internet, 1200, due on the 15th each month
Capture: I understood a recurring internet bill: 1200 due on day 15. Save? (yes/no)
User: yes
Reminder: Saved the bill and scheduled an approved due-date reminder.

User: wrap up my day
Reminder: Evening review - completed: biology notes; postponed: walk;
         tomorrow's top 3: electricity bill, biology revision, walk.
```

See `assets/demo-script.md` for a compact walkthrough suitable for a live
hackathon demo.
