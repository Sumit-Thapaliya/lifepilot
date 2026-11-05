from pathlib import Path
import sqlite3
DB_PATH = Path(__file__).parent / "data" / "lifepilot.db"
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row; return con
def init_db():
    with connect() as con:
        con.executescript('''CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, deadline TEXT, category TEXT DEFAULT 'personal', priority INTEGER DEFAULT 3, notes TEXT DEFAULT '', estimated_minutes INTEGER DEFAULT 30, status TEXT DEFAULT 'pending', approved INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS bills (id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount REAL DEFAULT 0, due_date TEXT, recurrence TEXT DEFAULT 'monthly', approved INTEGER DEFAULT 1); CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY, message TEXT NOT NULL, remind_at TEXT, kind TEXT DEFAULT 'general', sent INTEGER DEFAULT 0, approved INTEGER DEFAULT 0); CREATE TABLE IF NOT EXISTS daily_plans (id INTEGER PRIMARY KEY, plan_date TEXT, content TEXT NOT NULL, approved INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP); CREATE TABLE IF NOT EXISTS memory (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
        try: con.execute('ALTER TABLE tasks ADD COLUMN postponed_to TEXT')
        except sqlite3.OperationalError: pass
init_db()

# Compatibility names used by API routes and services.
get_connection = connect
initialize_database = init_db
