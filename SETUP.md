# LifePilot — setup, step by step

Written for someone who has never run a Python project. If a step fails, the
troubleshooting table at the end covers the usual causes.

**Time:** about 10 minutes, most of it downloading Python.

---

## What you are installing

Three things, in this order:

1. **Python** — the language the project is written in. You need it once.
2. **The project** — a folder of files you download as a ZIP.
3. **An API key** (optional) — makes the app understand times like "before bed".
   Everything works without it; it just understands less.

---

## Step 1 — Install Python

### Windows

1. Open <https://www.python.org/downloads/> and click the big yellow
   **Download Python 3.x** button.
2. Run the installer.
3. **Important:** on the first screen, tick the box
   **"Add python.exe to PATH"** at the bottom. If you miss it, you will have to
   reinstall — the `python` command will not work otherwise.
4. Click **Install Now** and wait.
5. **Close the Command Prompt and open a new one.** Windows only picks up the
   new PATH in terminals opened *after* the install.
6. Check it worked:

   ```
   python --version
   ```

   You should see something like `Python 3.12.4`.

   **If you instead see** *"Python was not found; run without arguments to
   install from the Microsoft Store"*, Windows is running a fake `python.exe`
   stub. Try `py --version` — if that prints a version, run everything in this
   guide with `py` instead of `python`, or turn the stub off. The full fix is in
   **The "Python was not found" error on Windows** near the end of this file.

### macOS

1. Open the **Terminal** app (press `Cmd+Space`, type `terminal`, Enter).
2. Type `python3 --version` and press Enter.
3. If you see `Python 3.10` or higher, you are done. If not, go to
   <https://www.python.org/downloads/> and run the macOS installer.

**On macOS, use `python3` and `pip3` everywhere this guide says `python` and
`pip`.** macOS reserves `python` for an old version.

### Linux

Open a terminal and run:

```
python3 --version
```

If it reports 3.10 or higher you are done. Otherwise:

```
sudo apt install python3 python3-venv python3-pip      # Debian / Ubuntu
sudo dnf install python3 python3-pip                    # Fedora
```

---

### You are seeing `>>>` — how to get out

If your prompt became `>>>`, you are inside Python's interactive shell, not
Windows. Type:

```
exit()
```

or press **Ctrl+Z then Enter**. Your normal prompt
`C:\Users\You\...>` comes back.

Every command in this guide is typed at the **Windows prompt**, never at `>>>`.

### Version flags

```
python --version      correct
python -V             correct
python --v            wrong  (-v alone means "verbose", and prints noise)
```

---

## Step 2 — Download the project

In this workspace, right-click **`lifepilot.zip`** and choose **Download**.
Save it somewhere you will find again — for example your **Desktop**.

Then **unzip it**:

| System | How |
|---|---|
| Windows | Right-click the ZIP → **Extract All…** → **Extract** |
| macOS | Double-click the ZIP — it becomes a folder next to it |
| Linux | `unzip lifepilot.zip` |

You now have a folder called `lifepilot` containing:

```
lifepilot/
├── README.md            what the project is
├── SETUP.md             this file
├── requirements.txt     the Python packages it needs
├── .env.example         template for your settings   <-- used in Step 5
├── backend/             the application
├── switch/              the Switch template
├── tests/               133 automated tests
└── assets/              diagrams and the demo script
```

> **Do not** work inside the ZIP. Unzip first, then use the folder.

---

## Step 3 — Open a terminal in that folder

This is the step people get wrong most often. Every command below must be run
**from inside the `lifepilot` folder**.

### Windows

1. Open the unzipped `lifepilot` folder in File Explorer.
2. Click the address bar at the top (where the path is shown).
3. Type `cmd` and press Enter.

A Command Prompt opens, already pointing at the right folder.

### macOS

1. Open the `lifepilot` folder in Finder.
2. Right-click a file inside it → **Services** → **New Terminal at Folder**.
   (Or drag the folder onto the Terminal icon in the Dock.)

### Linux

Right-click inside the folder → **Open in Terminal**.

### Check you are in the right place

```
dir        (Windows)
ls         (macOS / Linux)
```

You should see `README.md`, `requirements.txt` and a folder called `backend`.
If you see a single folder called `lifepilot`, you are one level up — go into it
with `cd lifepilot` and check again.

---

## Step 4 — Create a virtual environment and install

A *virtual environment* is a private copy of Python for this project, so nothing
else on your machine is affected. Do this once.

**Windows** (Command Prompt):

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

What you should see:

* After the `activate` line, your prompt gains a `(.venv)` prefix. That is how
  you know the environment is active.
* After `pip install`, a series of `Downloading…` lines, ending in
  `Successfully installed fastapi… uvicorn…` and the rest.

If you open a **new** terminal later, you must run the `activate` line again.
It does not stay on.

### If `pip install` fails while building "pillow" or "pyyaml"

You may see red text like:

```
Building wheel for pillow (pyproject.toml) ... error
The headers or library files could not be found for zlib
error: Microsoft Visual C++ 14.0 or greater is required
ERROR: Failed building wheel for pillow
ERROR: Failed building wheel for pyyaml
```

**What happened:** you are on a *very new* Python (3.15 is the usual one) and
those two packages had not yet published prebuilt versions for it, so pip tried
to compile them from source — which needs a C++ compiler you do not have.

**This is already fixed in `requirements.txt`.** If you saw this error, your
copy of the project is older than the fix. Update two files:

* `requirements.txt` — now asks for `pillow>=10,<14` (version 13 ships
  prebuilt files for 3.15) and picks a pure-Python YAML parser on 3.15.
* `tests/yaml_shim.py` — new file, lets the tests read the YAML template
  without PyYAML.

Then, in the same window:

```
pip install -r requirements.txt
```

If you would rather not fetch new files, the alternative is to install
**Python 3.13 or 3.14** from <https://www.python.org/downloads/> and rebuild
the environment with it:

```
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Everything in this project runs on 3.10 or newer; 3.13/3.14 are the versions
the test suite was run against.

---

## Step 5 — Add your API key (optional)

### 5a. Get a free key

Go to <https://console.groq.com/keys>, sign up with an email address, and click
**Create API Key**. Copy the key — it starts with `gsk_`.

No credit card is needed. Free alternatives are listed in the README.

### 5b. Put it in a file, not in the terminal

Typing a key into a command puts it in your shell history, where it stays for
ever and shows up in screenshots and demo recordings. Use the `.env` file
instead.

**Copy the template to a real file:**

```
copy .env.example .env        (Windows)
cp .env.example .env          (macOS / Linux)
```

**Open `.env` in a plain text editor:**

| System | Editor |
|---|---|
| Windows | Notepad — right-click `.env` → **Open with** → **Notepad** |
| macOS | TextEdit — right-click → **Open With** → **TextEdit** |
| Any | VS Code: `code .env` |

> On Windows, if you cannot see `.env`, enable
> **View → Show → File name extensions** in File Explorer. A file called
> `.env` has no name, only an extension.

**Find these two lines near the top and fill them in:**

```
LIFEPILOT_LLM_PROVIDER=groq
LIFEPILOT_LLM_API_KEY=paste-your-key-here
```

So it looks like this when you are done:

```
LIFEPILOT_LLM_PROVIDER=groq
LIFEPILOT_LLM_API_KEY=gsk_abc123yourrealkeyhere
```

Rules that matter:

* **No spaces** around the `=`.
* **No quotes** needed around the key.
* Keep it on **one line**.
* Save the file.

**Never rename `.env.example`.** Leave it as the template and create `.env`
as a separate file. `.env` is already excluded from git, so the key is never
committed.

### 5d. What to do with all the other blank lines

**Nothing. Leave them blank.** Every one of them is optional, and a blank line
means "use the default". Here is what each one would do if you filled it in:

| Line | Leave blank? | What filling it does |
|---|---|---|
| `LIFEPILOT_LLM_MODEL` | **Yes** | Blank uses the provider's default (`llama-3.3-70b-versatile` on Groq). Only set it to try a different model. |
| `LIFEPILOT_LLM_BASE_URL` | **Yes** | Only for a local model (Ollama). Blank picks the provider's own URL. |
| `LIFEPILOT_DISCORD_WEBHOOK` | **Yes** | Sends reminders into a Discord channel. Blank keeps them in `backend/data/outbox.log`. |
| `LIFEPILOT_SLACK_WEBHOOK` | **Yes** | Same, for Slack. Use one channel or none — not both. |
| `LIFEPILOT_SWITCH_WEBHOOK` | **Yes** | Same, for a Switch webhook URL. |
| `LIFEPILOT_TICK_INTERVAL=60` | **Keep the 60** | Seconds between reminder checks. 60 is fine. |
| `LIFEPILOT_TASK_WINDOW=1` | **Keep the 1** | Warns 1 day ahead, so you hear about a task the day before it is due. Set `0` for "only on the due date". |
| `LIFEPILOT_BILL_WINDOW=3` | **Keep the 3** | Warns 3 days before a bill is due. |
| `LIFEPILOT_TICK=1` | **Keep the 1** | `1` = reminders run automatically. `0` = switch the clock off. |
| `LIFEPILOT_DB` | **Yes** | Blank uses `backend/data/lifepilot.db` inside the project. |
| `LIFEPILOT_TIMEZONE` | **Set it** | Your own timezone, e.g. `Asia/Kathmandu`. Gets `UTC` otherwise. |
| `TESSERACT_CMD` | **Yes** | Only if Tesseract is installed somewhere unusual. |

So after Step 5b, only **three** lines in your `.env` differ from the template:

```
LIFEPILOT_LLM_PROVIDER=groq
LIFEPILOT_LLM_API_KEY=gsk_...
LIFEPILOT_TIMEZONE=Asia/Kathmandu
```

Everything else stays exactly as it came.

> Blank values can never break the app: they are read as "not configured" and
> the built-in default is used instead. This is covered by the test
> `test_every_optional_setting_can_be_left_blank`.

### 5c. Skip this step entirely if you prefer

Leave `LIFEPILOT_LLM_PROVIDER` blank. LifePilot then uses its built-in keyword
rules. It still works — it just cannot tell that "before bed" means evening.
The interface shows a **RULES** badge instead of **MODEL**, so you always know
which one is running.

---

---

## Step 6a — Check your setup (do this first)

Before starting the server, run this from inside the `lifepilot` folder with
`(.venv)` active:

```
python -m backend.main --check
```

It reads your `.env` and reports what it found:

```
LifePilot setup check
==========================================================
[  OK  ] Python                     3.13.16
[  OK  ] Virtual environment        active
[  OK  ] .env file                  C:\Users\you\Desktop\lifepilot\.env
[  OK  ] Language model provider    groq
[  OK  ] API key                    gsk_...1234 (hidden)
[] Model                      llama-3.3-70b-versatile
[] Endpoint                   https://api.groq.com/openai/v1
[  OK  ] Understanding engine       MODEL - key found
[  OK  ] Database                   lifepilot.db
[] Reminder clock             every 60s when the app runs
[] Task warning window         1 day(s) ahead
[] Bill warning window         3 day(s) ahead
[] Reminder delivery          outbox.log (no webhook)
[  OK  ] Switch template            found
==========================================================
Send one test request to the model? [y/N]
```

Type **y** to send one real request. This is the only way to know the key is
valid rather than merely present. It costs one API call.

| `--check` says | Meaning |
|---|---|
| `.env file — not found` | The file is missing, or is named `.env.txt`. Enable file extensions and rename it. |
| `API key — missing for this provider` | `LIFEPILOT_LLM_PROVIDER` is set but `LIFEPILOT_LLM_API_KEY` is empty. |
| `'grok' is not a known provider` | Typo. Valid: `groq`, `gemini`, `openrouter`, `ollama`, `openai`, `anthropic`. |
| `the key was rejected (401)` | The key was not copied whole, or was revoked. Make a new one. |
| `the model name was not found` | `LIFEPILOT_LLM_MODEL` names a model your provider does not offer. Clear it to use the default. |
| `no network route` | The machine is offline. Use `LIFEPILOT_LLM_PROVIDER=ollama` instead. |
| `RULES — no key, works offline` | Not an error. The app runs on keyword rules. |

Your key is always shown as `gsk_...1234` — the first four and last four
characters only. It is never printed in full, so the output is safe to paste
into a chat or a bug report.

## Step 6 — Run it

With `(.venv)` showing in your prompt, from inside the `lifepilot` folder:

```
uvicorn backend.main:app --reload
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

Open your browser at **<http://localhost:8000>**.

> **Use `127.0.0.1` or `localhost`, not a network address.** Other devices cannot
> reach it, and it is not exposed to the internet.

Stop the server with **Ctrl+C** in the terminal.

### Check the key was picked up

In the page header, the badge next to **Parse a sentence** reads:

* **MODEL** — the key works. You are getting time-of-day inference.
* **RULES** — no key found; the built-in rules are being used.

Or from a second terminal:

```
curl http://localhost:8000/health      (macOS / Linux / Windows 10+)
```

Look for `"mode": "model"` and `"provider": "groq"`. If it says
`"mode": "rules"`, see the troubleshooting table.

---

## Step 7 — Try it

In the page:

1. Type `read a book before bed` and click **Parse**.
   With a model you should see **WHEN: 20:30** and a one-line reason.
2. Edit anything that is wrong — every field is editable.
3. Click **Save this task**. Nothing is stored until you click.
4. In the **Assistant** panel type `what is LifePilot?` and press Enter.
   You get a real answer; no task proposal is created.
5. In the **Assistant** panel type `add a task to feed the dog` and press Enter.
   The agent proposes; reply `yes` to save, `no` to discard.
6. Press **Progress check** in Quick actions to preview the periodic question
   for one open task. The automatic scheduler delivers it without spamming.

---

## Step 8 — Other commands

All of these run from the `lifepilot` folder with `(.venv)` active.

| Command | What it does |
|---|---|
| `python -m backend.main --check` | Diagnose your `.env` and test the key. Run this first. |
| `uvicorn backend.main:app --reload` | Start the app. Reminders run on a timer inside it. |
| `python -m backend.main --demo` | Print the whole workflow in the terminal. No browser needed. |
| `python -m backend.main --watch --interval 30` | Run the reminder clock as its own process. |
| `pytest -q` | Run the 133 tests. Should end `133 passed`. |
| `deactivate` | Leave the virtual environment. |

Copy this project to another machine and you only repeat Steps 2–6.

---

### The "Python was not found" error on Windows

If you see this:

```
C:\Users\You\Desktop\projects\lifepilot>python -m venv .venv
Python was not found; run without arguments to install from the Microsoft Store,
or disable this shortcut from Settings > Apps > Advanced app settings > App
execution aliases.
```

Windows is not saying "Python is broken". It is running a **stub** that opens
the Microsoft Store, because no real Python was found. Work through these in
order.

#### Check 1 — is Python installed at all?

In the same Command Prompt, run:

```
py --version
```

* **You see a version like `Python 3.12.4`** → Python *is* installed. Only the
  `python` alias is broken. Jump to **Fix B**.
* **You see the same Microsoft Store message, or
  `'py' is not recognized`** → Python is genuinely not installed. Do **Fix A**.

#### Fix A — install Python properly

1. Go to <https://www.python.org/downloads/>.
2. Click the big yellow **Download Python 3.x** button.
3. Run the downloaded `python-3.x.x-amd64.exe`.
4. **On the very first screen**, at the bottom, tick
   **"Add python.exe to PATH"**.
   This is the single most important click in the whole setup.
5. Click **Install Now** and wait for "Setup was successful".
6. **Close the Command Prompt window completely and open a new one.**
   PATH changes do not reach terminals that were already open.
7. Verify:

   ```
   python --version
   ```

#### Fix B — turn off the Microsoft Store stub

1. Open **Settings** (press `Win`, type `settings`).
2. Go to **Apps** → **Advanced app settings** → **App execution aliases**.
3. Scroll to **App Installer** and switch **off** both:
   * `python.exe`
   * `python3.exe`
4. **Close and reopen** the Command Prompt.
5. Verify with `python --version` or `py --version`.

Typing `python` in a fresh window should now print a version number, not a
shopping page.

#### Fix C — just use `py` instead

The **Python Launcher** (`py`) ships with the python.org installer and almost
always works even when `python` does not. Every command in this guide works
with it:

```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
py -m backend.main --check
```

Note that once the virtual environment is **active**, `python` works normally
inside it — the environment provides its own `python.exe`. So in practice you
only need `py` for the very first `py -m venv .venv` line.

#### Still stuck

Check where Windows is looking:

```
where python
```

* `C:\Users\...\AppData\Local\Microsoft\WindowsApps\python.exe` → this is
  the stub. Do Fix B, or do Fix A and reopen the terminal.
* A path under `C:\Users\...\AppData\Local\Programs\Python\Python3xx\`
  → Python is installed; the terminal is stale. Reopen it.

---

## Troubleshooting

| What you see | What it means | Fix |
|---|---|---|
| `Python was not found; run without arguments to install from the Microsoft Store` | Windows is running a stub, not Python | See **The "Python was not found" error on Windows** above |
| `'uvicorn' is not recognized` | The virtual environment is not active | Run the `activate` line from Step 4 again |
| `ModuleNotFoundError: No module named 'backend'` | You are in the wrong folder | `cd` into the folder that contains `backend/` |
| `ModuleNotFoundError: No module named 'fastapi'` | Packages not installed, or venv not active | Activate, then `pip install -r requirements.txt` |
| `[Errno 48] Address already in use` (macOS/Linux) or `10048` (Windows) | Something else is on port 8000 | `uvicorn backend.main:app --port 8001`, then open `localhost:8001` |
| `source: command not found` on Windows | You used the macOS command | Use `.venv\Scripts\activate` |
| Page loads but the badge says **RULES** | The key was not read | Check `.env` is in the same folder as `requirements.txt`, has no spaces around `=`, and that you restarted the server |
| `401` or `Invalid API key` in the terminal | The key is wrong or expired | Make a new key at console.groq.com/keys |
| Page will not load at all | The server is not running | Check the terminal for red text; the server must stay running |
| `Permission denied` on `activate` (macOS/Linux) | The file is not executable | `chmod +x .venv/bin/activate` then retry |

Still stuck: run `pytest -q`. If those pass, the code is fine and the problem is
in the environment, not the project.

---

## Keeping the key private

* The key lives **only** in `.env`, which is excluded from git.
* Never paste a key into a chat, a screenshot, a demo video, or a terminal
  command — shell history keeps it for ever.
* If a key ever leaks, revoke it at <https://console.groq.com/keys> and make a
  new one. That takes about ten seconds and costs nothing.
* To confirm nothing is exposed, run `git status` — `.env` must never appear in
  the list.
