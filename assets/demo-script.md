# LifePilot — demo script

Two ways to demo. Both take under two minutes.

## Option A — no chat app needed (recommended for judges on a laptop)

```bash
pip install -r requirements.txt
python -m backend.main --demo
```

Narrate as it prints:

1. **Capture** proposes a task and explicitly says nothing was saved.
2. The user says yes — only then does the task appear, with an ID.
3. **Planner** proposes a daily plan capped at three priorities, reports two
   clashing deadlines, and suggests what to postpone. Nothing saved yet.
4. The user says yes — the plan gets an ID.
5. **Planner** builds a study plan from an exam date: 10 days left, 20 hours →
   2 hours per day, plus one honest line of advice.
6. **Reminder** posts bill due dates and changes nothing.
7. **Reminder** posts the morning briefing and the evening review.
8. **Reminder** asks before postponing anything.

The line to land: *"Every single step asked first. That is the whole product."*

## Option B — inside the Switch room

1. Open `#lifepilot`. Show the kickoff message with the three agents present.
2. Say: `add a task — submit the lab report by Friday, high priority`
   - Point at Capture's field-by-field reading and the confirmation question.
3. Reply `yes`. Show the saved task ID.
4. Say: `plan my day`
   - Show the three-priority cap, the conflict warning, and the postponement suggestion.
5. Reply `yes`.
6. Say: `study plan — biology exam on <a date 10 days out>, 20 hours available`
   - Show days left and hours per day.
7. Say: `track a bill — internet, 1200, due on the 15th, monthly`, approve it.
8. Say: `morning briefing` — show top three, bills due, mock weather.
9. Say: `wrap up my day` — show completed, postponed, tomorrow's top three.
10. Say: `postpone 1 to tomorrow` — and point out it *asks before moving anything*.

## Beats worth saying out loud

- "There is no app to install. The chat room is the app."
- "Three agents, three jobs — not one bot pretending to be three."
- "It runs with no paid API. Mock weather, local OCR, rule-based parsing."
- "Nothing is saved until I say yes. That's enforced in the code, not just the prompt."
- "General questions get answers. Only actionable text becomes a task proposal."
- "The scheduler checks in on one open task every few hours and never edits it."
- "Assistant chat reads a photo and shows Add these and Ignore these decisions with reasons. Only the selected real tasks are saved after I approve."

## Screenshot checklist

- [ ] Kickoff message with all three agents
- [ ] Capture's proposal with "Nothing is saved yet"
- [ ] The same task after `yes`, showing the saved ID
- [ ] Planner's three-priority plan with a conflict warning
- [ ] `python -m backend.main --demo` output
- [ ] A general question answered by Assistant with no approval panel
- [ ] Progress check preview in Quick actions
- [ ] Assistant chat showing Add these / Ignore these decisions, reasons, and Add selected tasks approval
- [ ] `pytest -q` showing 148 passed
