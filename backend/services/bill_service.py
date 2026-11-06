"""Bill service: recurring bills, due-date maths, and reminder scheduling.

Mock data lives here so the demo never depends on a paid API. Real bills are
created from the user's own messages via the Capture agent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..database import connect

# Used by `--demo` and by the morning briefing when no bills exist yet.
MOCK_BILLS: list[dict] = [
    {"name": "Rent", "amount": 15000, "recurrence": "monthly", "day_of_month": 1},
    {"name": "Internet", "amount": 1200, "recurrence": "monthly", "day_of_month": 15},
    {"name": "Electricity", "amount": 2450, "recurrence": "monthly", "day_of_month": 8},
]


def _next_occurrence(day_of_month: int) -> str:
    """The next date this month or next month that matches the given day."""
    today = date.today()
    candidate = today.replace(day=min(day_of_month, 28))
    if candidate < today:
        next_month = (today.replace(day=1) + timedelta(days=32)).replace(
            day=min(day_of_month, 28)
        )
        return str(next_month)
    return str(candidate)


def create_bill(data: dict) -> dict:
    with connect() as con:
        cursor = con.execute(
            "INSERT INTO bills (name, amount, due_date, recurrence, approved)"
            " VALUES (?,?,?,?,?)",
            (
                data["name"],
                data.get("amount", 0),
                data.get("due_date"),
                data.get("recurrence", "monthly"),
                int(data.get("approved", True)),
            ),
        )
        row = con.execute("SELECT * FROM bills WHERE id=?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def list_bills() -> list[dict]:
    with connect() as con:
        return [
            dict(row)
            for row in con.execute("SELECT * FROM bills ORDER BY COALESCE(due_date, '9999-12-31')")
        ]


def days_until(due_date: str | None) -> int | None:
    """Whole days from today to a due date, or None when unparseable."""
    if not due_date:
        return None
    try:
        due = datetime.fromisoformat(str(due_date)).date()
    except ValueError:
        return None
    return (due - date.today()).days


def upcoming_bills(within_days: int = 7) -> list[dict]:
    """Bills due inside the window, soonest first."""
    scored = []
    for bill in list_bills():
        remaining = days_until(bill.get("due_date"))
        if remaining is not None and remaining <= within_days:
            scored.append({**bill, "days_until_due": remaining})
    return sorted(scored, key=lambda b: b["days_until_due"])


def due_reminder_text(bill: dict, days_before: int = 3) -> str:
    """One short sentence the Reminder agent can post as-is."""
    remaining = days_until(bill.get("due_date"))
    amount = f"{bill.get('amount', 0):,.0f}"
    if remaining is None:
        return f"{bill['name']}: due date unknown — set one and I'll remind you."
    if remaining < 0:
        return f"{bill['name']} ({amount}) is {abs(remaining)} day(s) overdue."
    if remaining == 0:
        return f"{bill['name']} ({amount}) is due today."
    if remaining <= days_before:
        return f"{bill['name']} ({amount}) is due in {remaining} day(s)."
    return f"{bill['name']} ({amount}) is due in {remaining} days — no action needed yet."


def seed_mock_bills(today: str | None = None) -> list[dict]:
    """Create the demo bills if the bills table is empty."""
    if list_bills():
        return list_bills()
    created = []
    for mock in MOCK_BILLS:
        created.append(
            create_bill(
                {
                    "name": mock["name"],
                    "amount": mock["amount"],
                    "due_date": _next_occurrence(mock["day_of_month"]),
                    "recurrence": mock["recurrence"],
                    "approved": True,
                }
            )
        )
    return created


# Compatibility aliases kept for existing imports.
bills = list_bills
create = create_bill
