"""LLM client — the model does the understanding, not the storing.

Why this file exists
--------------------
LifePilot originally guessed meaning with keyword tables. That is cheap and
testable, but it cannot know that "read a book before bed" happens at night.
Only a language model can infer that, because it requires knowing what beds
are for.

So the split is:

    the MODEL decides what the words mean
    THIS CODE decides what is allowed to be stored

This module is a thin, provider-agnostic client. It speaks the two shapes that
almost every provider implements:

    openai      POST {base}/chat/completions   (OpenAI, Groq, Together,
                OpenRouter, Ollama, LM Studio, vLLM, llama.cpp server)
    anthropic   POST {base}/v1/messages        (Claude)

Configure one environment variable and the whole app upgrades:

    LIFEPILOT_LLM_PROVIDER=openai
    LIFEPILOT_LLM_API_KEY=sk-...
    LIFEPILOT_LLM_MODEL=gpt-4o-mini

    # or a free local model, no key, no network:
    LIFEPILOT_LLM_PROVIDER=openai
    LIFEPILOT_LLM_BASE_URL=http://localhost:11434/v1
    LIFEPILOT_LLM_MODEL=llama3.1

With nothing configured, ``available()`` is False and the caller falls back to
the rule-based parser. The app never breaks; it only gets less clever.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Optional

ANTHROPIC_DEFAULT = "https://api.anthropic.com"
TIMEOUT_SECONDS = 25

# Every one of these has a standing free tier except openai/anthropic.
# provider -> (base url, default model, needs a key, key env var names)
PRESETS: dict[str, tuple[str, str, bool, tuple[str, ...]]] = {
    "groq": (
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile",
        True,
        ("LIFEPILOT_LLM_API_KEY", "GROQ_API_KEY"),
    ),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.5-flash",
        True,
        ("LIFEPILOT_LLM_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
    ),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        "meta-llama/llama-3.3-70b-instruct:free",
        True,
        ("LIFEPILOT_LLM_API_KEY", "OPENROUTER_API_KEY"),
    ),
    "ollama": (
        "http://localhost:11434/v1",
        "llama3.1",
        False,
        ("LIFEPILOT_LLM_API_KEY",),
    ),
    "openai": (
        "https://api.openai.com/v1",
        "gpt-4o-mini",
        True,
        ("LIFEPILOT_LLM_API_KEY", "OPENAI_API_KEY"),
    ),
    "anthropic": (
        ANTHROPIC_DEFAULT,
        "claude-3-5-haiku-latest",
        True,
        ("LIFEPILOT_LLM_API_KEY", "ANTHROPIC_API_KEY"),
    ),
}

STATE = {"calls": 0, "failures": 0, "last_error": None, "last_model": None}


# ------------------------------------------------------------------ settings

def provider() -> str:
    return os.environ.get("LIFEPILOT_LLM_PROVIDER", "").strip().lower()


def model_name() -> str:
    explicit = os.environ.get("LIFEPILOT_LLM_MODEL", "").strip()
    if explicit:
        return explicit
    preset = PRESETS.get(provider())
    return preset[1] if preset else "gpt-4o-mini"


def api_key() -> Optional[str]:
    """Look in our own variable first, then the provider's conventional one."""
    preset = PRESETS.get(provider())
    names = preset[3] if preset else ("LIFEPILOT_LLM_API_KEY", "OPENAI_API_KEY")
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def base_url() -> str:
    explicit = os.environ.get("LIFEPILOT_LLM_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    preset = PRESETS.get(provider())
    return preset[0] if preset else PRESETS["openai"][0]


def available() -> bool:
    """True only when we have enough configuration to make a real call."""
    preset = PRESETS.get(provider())
    if preset is None:
        return False
    needs_key = preset[2]
    if not needs_key:
        return True  # local model, e.g. Ollama
    # A self-hosted endpoint on this machine needs no key either.
    local = any(host in base_url() for host in ("localhost", "127.0.0.1", "0.0.0.0"))
    return bool(api_key() or local)


def presets() -> dict:
    """Expose the supported providers so the README and UI stay truthful."""
    return {
        name: {
            "base_url": data[0],
            "default_model": data[1],
            "needs_key": data[2],
        }
        for name, data in PRESETS.items()
    }


def status() -> dict:
    return {
        "available": available(),
        "provider": provider() or None,
        "model": model_name() if available() else None,
        "base_url": base_url() if available() else None,
        "calls": STATE["calls"],
        "failures": STATE["failures"],
        "last_error": STATE["last_error"],
    }


# ------------------------------------------------------------------ transport

def _post(url: str, body: dict, headers: dict) -> dict:
    """One HTTPS POST. Isolated so tests can monkeypatch it."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "LifePilot/1.0", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def complete(system: str, user: str, json_mode: bool = True) -> Optional[str]:
    """Ask the model one question. Returns raw text, or None on any failure.

    Returning None rather than raising keeps the caller's fallback path simple:
    anything that goes wrong means "use the rules".
    """
    if not available():
        return None

    STATE["calls"] += 1
    STATE["last_model"] = model_name()

    try:
        if provider() == "anthropic":
            body = {
                "model": model_name(),
                "max_tokens": 700,
                "system": system + ("\nReply with JSON only." if json_mode else ""),
                "messages": [{"role": "user", "content": user}],
            }
            headers = {
                "x-api-key": api_key() or "",
                "anthropic-version": "2023-06-01",
            }
            data = _post(f"{base_url()}/v1/messages", body, headers)
            blocks = data.get("content") or []
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        else:
            body = {
                "model": model_name(),
                "temperature": 0,
                "max_tokens": 700,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            if json_mode:
                body["response_format"] = {"type": "json_object"}
            headers = {}
            if api_key():
                headers["Authorization"] = f"Bearer {api_key()}"
            data = _post(f"{base_url()}/chat/completions", body, headers)
            text = data["choices"][0]["message"]["content"]

        text = (text or "").strip()
        if not text:
            raise ValueError("empty completion")
        return text

    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, KeyError) as exc:
        STATE["failures"] += 1
        STATE["last_error"] = f"{type(exc).__name__}: {exc}"
        return None


def complete_json(system: str, user: str) -> Optional[dict]:
    """Ask for JSON and parse it defensively.

    Models sometimes wrap JSON in prose or code fences despite instructions.
    We extract the outermost object rather than trusting the whole string.
    """
    raw = complete(system, user, json_mode=True)
    if raw is None:
        return None

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    STATE["failures"] += 1
    STATE["last_error"] = "model did not return parseable JSON"
    return None
