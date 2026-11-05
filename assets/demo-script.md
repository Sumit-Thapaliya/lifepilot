# Life Pilot demo script

## Local setup

```powershell
cd lifepilot
python -m venv .venv
.venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

In another terminal, run `python -m backend.main --demo` to exercise a local
demo without a frontend. The Switch room is the chat UI.

## Walkthrough

1. Open the shared Switch room and show the kickoff message.
2. Say: `add a task - submit the lab report by Friday, high priority`.
3. Point out Capture's extracted title, deadline, category, priority, and the
   explicit confirmation question. Reply `yes` and show the saved task.
4. Say: `plan my day`. Show the Planner's maximum-three proposal and approve it.
5. Say: `track a bill - internet, 1200, due on the 15th monthly`. Approve the
   bill and show the scheduled reminder.
6. Upload a photo of a handwritten deadline. Show OCR extraction and the same
   confirmation gate before saving.
7. Say: `wrap up my day` and show completed tasks, postponed tasks, and
   tomorrow's top three priorities.

The demo is fully local: FastAPI, SQLite, and optional local OCR. No paid
external API is required, and no frontend build is needed.
