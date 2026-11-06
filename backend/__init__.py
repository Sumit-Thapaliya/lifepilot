"""LifePilot backend package.

The .env file is loaded here, at import time, so every service that reads an
environment variable sees the values from the file without each one having to
remember to load it.
"""

from . import env_loader as _env_loader  # noqa: F401  (import has side effects)

__all__ = ["_env_loader"]
