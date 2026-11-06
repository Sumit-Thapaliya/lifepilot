"""Load YAML in the tests, whatever parser is installed.

PyYAML is the preferred parser, but it has no Windows wheels for Python 3.15
and cannot build without Visual C++ — and the template is only parsed by the
tests, never by the running app. So on a machine where PyYAML is unavailable we
fall back to ``ruamel.yaml``, which is pure Python and installs anywhere.

The tests do not care which one ran; both return plain dicts.
"""

from __future__ import annotations

from pathlib import Path


def safe_load(path: str | Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError:
        from ruamel.yaml import YAML  # type: ignore

        return YAML(typ="safe").load(text)
    return yaml.safe_load(text)
