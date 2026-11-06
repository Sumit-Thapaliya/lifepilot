"""Photo OCR service.

Uses a local Tesseract install when available and degrades honestly when it is
not: it reports ``ocr_available: false`` instead of pretending it read an
empty image. No paid OCR API is used.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile

MAX_PROPOSALS = 10


def ocr_available() -> bool:
    """True when Pillow and pytesseract can both be imported."""
    return (
        importlib.util.find_spec("pytesseract") is not None
        and importlib.util.find_spec("PIL") is not None
    )


def extract_text(path: str) -> str:
    """Return raw OCR text, or an empty string when OCR is unavailable."""
    try:
        import pytesseract
        from PIL import Image

        return pytesseract.image_to_string(Image.open(path)).strip()
    except Exception:
        return ""


def extract_tasks_from_photo(content: bytes, filename: str, approved: bool = False) -> dict:
    """OCR an uploaded image and propose one task per readable line.

    A proposal is returned even for a single line, and nothing is saved here:
    the Capture agent confirms with the user first.
    """
    from .task_service import parse_task_text

    suffix = os.path.splitext(filename)[1] or ".png"
    handle, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(handle, "wb") as file:
            file.write(content)

        if not ocr_available():
            return {
                "ocr_available": False,
                "filename": filename,
                "text": "",
                "proposals": [],
                "requires_confirmation": False,
                "reply": (
                    "I can't read images on this machine because Tesseract isn't "
                    "installed. Paste the text instead and I'll structure it."
                ),
            }

        text = extract_text(temp_path)
        if not text:
            return {
                "ocr_available": True,
                "filename": filename,
                "text": "",
                "proposals": [],
                "requires_confirmation": False,
                "reply": "I read the image but found no readable text. Try a sharper photo.",
            }

        proposals = [
            parse_task_text(line)
            for line in text.splitlines()
            if len(line.strip()) > 3
        ][:MAX_PROPOSALS]

        return {
            "ocr_available": True,
            "filename": filename,
            "text": text,
            "proposals": proposals,
            "requires_confirmation": True,
            "approved": approved,
            "reply": (
                f"I read {len(proposals)} line(s) from the photo. "
                "Reply 'save' to store them as tasks, or paste corrections."
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
