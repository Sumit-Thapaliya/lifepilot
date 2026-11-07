"""Photo OCR service.

Prefers RapidOCR, a pip-only OCR engine that needs no system binary. Tesseract
remains available as an optional fallback for machines that already have it.
No paid OCR API is used, and OCR never writes to the database.

The OCR text is then classified by ``understanding_service``: the configured
model marks each line as a real task or not a task, with reasons. Keyword rules
remain the offline fallback.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import tempfile

from . import understanding_service

MAX_PROPOSALS = 10
_OCR_ENGINE_CACHE: dict[str, object] = {}

# RapidOCR logs its bundled ONNX models on first use. The CLI report and
# /health stay clean; the engine still works exactly the same way.
logging.getLogger("RapidOCR").setLevel(logging.ERROR)


def _engine_preference() -> str:
    """Return auto, rapidocr, tesseract, or none."""
    value = os.environ.get("LIFEPILOT_OCR_ENGINE", "auto").strip().lower()
    return value if value in {"auto", "rapidocr", "tesseract", "none"} else "auto"


def _configure_tesseract() -> None:
    """Honour TESSERACT_CMD when the binary is in an unusual location."""
    command = os.environ.get("TESSERACT_CMD", "").strip()
    if command:
        import pytesseract

        pytesseract.pytesseract.tesseract_cmd = command


def _tesseract_available() -> bool:
    """True when pytesseract, Pillow, and the Tesseract binary are usable."""
    if (
        importlib.util.find_spec("pytesseract") is None
        or importlib.util.find_spec("PIL") is None
    ):
        return False
    try:
        import pytesseract
        from PIL import Image  # noqa: F401

        _configure_tesseract()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _rapidocr_available() -> bool:
    """True when a supported RapidOCR package is installed by pip."""
    return (
        importlib.util.find_spec("rapidocr") is not None
        or importlib.util.find_spec("rapidocr_onnxruntime") is not None
    )


def _rapidocr_engine() -> object | None:
    """Load and cache the local RapidOCR engine, or report that it failed."""
    if "rapidocr" in _OCR_ENGINE_CACHE:
        return _OCR_ENGINE_CACHE["rapidocr"]
    if not _rapidocr_available():
        return None
    try:
        try:
            from rapidocr import RapidOCR
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore

        engine = RapidOCR()
    except Exception:
        return None
    _OCR_ENGINE_CACHE["rapidocr"] = engine
    return engine


def selected_engine() -> str | None:
    """Pick rapidocr, tesseract, or none according to config and availability.

    ``auto`` prefers RapidOCR because ordinary ``pip install -r
    requirements.txt`` is enough to enable it; Tesseract is used only when
    RapidOCR is missing or the user explicitly asks for it.
    """
    preference = _engine_preference()
    if preference == "none":
        return None
    if preference == "rapidocr":
        return "rapidocr" if _rapidocr_engine() is not None else None
    if preference == "tesseract":
        return "tesseract" if _tesseract_available() else None
    if _rapidocr_engine() is not None:
        return "rapidocr"
    if _tesseract_available():
        return "tesseract"
    return None


def ocr_available() -> bool:
    """True when a usable OCR engine is installed."""
    return selected_engine() is not None


def _tesseract_text(path: str) -> str:
    try:
        import pytesseract
        from PIL import Image

        _configure_tesseract()
        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception:
        return ""


def _rapidocr_lines(result: object) -> list[str]:
    """Normalise RapidOCR v3 output and the older tuple-based output."""
    txts = getattr(result, "txts", None)
    if txts:
        return [str(line).strip() for line in txts if str(line).strip()]

    # rapidocr_onnxruntime returns (rows, elapsed); each row is [box, text, score].
    if isinstance(result, tuple) and result:
        rows = result[0] or []
        lines: list[str] = []
        for row in rows:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                text = row[1]
                if isinstance(text, (list, tuple)) and text:
                    text = text[0]
                if str(text).strip():
                    lines.append(str(text).strip())
        return lines
    return []


def _rapidocr_text(path: str) -> str:
    engine = _rapidocr_engine()
    if engine is None:
        return ""
    try:
        result = engine(path)  # type: ignore[operator]
        return "\n".join(_rapidocr_lines(result)).strip()
    except Exception:
        return ""


def extract_text(path: str, engine: str | None = None) -> str:
    """Return raw OCR text, or an empty string when OCR is unavailable."""
    engine = engine or selected_engine()
    if engine == "rapidocr":
        text = _rapidocr_text(path)
        if text or not _tesseract_available():
            return text
        return _tesseract_text(path)
    if engine == "tesseract":
        return _tesseract_text(path)
    return ""


def status() -> dict:
    """What /health and the CLI report about the photo-to-tasks path."""
    engine = selected_engine()
    return {
        "available": engine is not None,
        "engine": (
            "RapidOCR" if engine == "rapidocr" else "Tesseract" if engine == "tesseract" else None
        ),
        "understanding": understanding_service.status()["mode"],
    }


def extract_tasks_from_photo(content: bytes, filename: str, approved: bool = False) -> dict:
    """OCR an image, find tasks in the text, and propose them. Never saves.

    The configured model classifies the OCR lines into tasks to ADD and lines
    to IGNORE, with a short reason for each. Python validates every proposed
    field. Without a model, line rules do the same job. The user still confirms
    before anything reaches SQLite.
    """
    suffix = os.path.splitext(filename)[1] or ".png"
    handle, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(content)

        engine = selected_engine()
        if engine is None:
            return {
                "ocr_available": False,
                "ocr_engine": None,
                "filename": filename,
                "text": "",
                "proposals": [],
                "classification": {
                    "add": [], "ignore": [], "engine": "none",
                    "engine_note": "No OCR engine is installed.", "reasoning": [],
                },
                "ignored_lines": [],
                "engine": "none",
                "engine_note": "No OCR engine is installed.",
                "requires_confirmation": False,
                "reply": (
                    "I can't read images on this machine yet. Run "
                    "pip install -r requirements.txt, then restart the app."
                ),
            }

        engine_label = "RapidOCR" if engine == "rapidocr" else "Tesseract"
        text = extract_text(temp_path, engine)
        if not text:
            return {
                "ocr_available": True,
                "ocr_engine": engine_label,
                "filename": filename,
                "text": "",
                "proposals": [],
                "classification": {
                    "add": [], "ignore": [], "engine": "none",
                    "engine_note": "OCR found no readable text.", "reasoning": [],
                },
                "ignored_lines": [],
                "engine": "none",
                "engine_note": "OCR found no readable text.",
                "requires_confirmation": False,
                "reply": "I read the image but found no readable text. Try a sharper photo.",
            }

        classified = understanding_service.classify_photo_text(
            text, limit=MAX_PROPOSALS
        )
        add = classified["add"]
        ignore = classified["ignore"]
        proposals = [
            {key: value for key, value in item.items()
             if key not in {"reason", "source_text"}}
            for item in add
        ]
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        classification = {
            "add": add,
            "ignore": ignore,
            "engine": classified["engine"],
            "engine_note": classified["engine_note"],
            "reasoning": classified.get("reasoning", []),
            "ocr_engine": engine_label,
        }

        return {
            "ocr_available": True,
            "ocr_engine": engine_label,
            "filename": filename,
            "text": text,
            "proposals": proposals,
            "classification": classification,
            "ignored_lines": ignore,
            "engine": classified["engine"],
            "engine_note": classified["engine_note"],
            "reasoning": classified.get("reasoning", []),
            "requires_confirmation": True,
            "approved": approved,
            "reply": (
                f"I read {len(lines)} line(s). {len(add)} look like real tasks; "
                f"{len(ignore)} are not tasks. Review below and add only what "
                "you choose. Nothing is saved yet."
            ),
        }
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# Compatibility aliases kept for existing imports.
extract_photo = extract_text
extract_photo_text = extract_text
extract_tasks = extract_tasks_from_photo
