"""Load .env before anything else in the backend runs.

Without this, putting a key in `.env` did nothing: nothing read the file. The
key had to be exported into the shell, where it then shows up in `env`, in
`history`, in a screenshot, or on a projector during a demo.

Order of precedence (highest first), which is what people expect:

    1. a real environment variable (exported in the shell)
    2. the .env file next to this project

So a one-off override still works, and the file is the normal place to keep it.

If python-dotenv is not installed we fall back to a tiny built-in reader, so
the feature never depends on an optional package.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_with_dotenv(path: Path) -> bool:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    load_dotenv(path, override=False)  # do not clobber exported variables
    return True


def _load_minimal(path: Path) -> None:
    """Parse KEY=value lines ourselves. Good enough for this project."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env(path: Path | None = None) -> bool:
    """Read .env if it exists. Returns True when a file was found."""
    target = path or (PROJECT_ROOT / ".env")
    if not target.exists():
        return False
    if not _load_with_dotenv(target):
        _load_minimal(target)
    return True


FOUND = load_env()
