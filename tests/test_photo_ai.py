"""Photo-to-tasks: OCR classification, approval gate, and Assistant chat UI."""

from __future__ import annotations

import re
from types import SimpleNamespace

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import llm_service, photo_service, task_service
from backend.ui import render_ui

client = TestClient(app)

OCR_TEXT = (
    "TODAY'S LIST\n"
    "Finish biology notes by Friday\n"
    "Pay electricity bill tomorrow\n"
    "Call dentist Monday 4pm\n"
    "Buy milk and bread\n"
    "Doodles and page 1"
)

EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")


class _FakeRapidOCR:
    """A pip-only engine stand-in, so tests never load ONNX models."""

    def __call__(self, _path):
        return SimpleNamespace(
            txts=("Buy milk", "Call dentist Monday 4pm"),
            scores=(0.99, 0.97),
            boxes=None,
        )


def _fake_ocr(monkeypatch, text: str = OCR_TEXT) -> None:
    monkeypatch.setattr(photo_service, "selected_engine", lambda: "rapidocr")
    monkeypatch.setattr(photo_service, "ocr_available", lambda: True)
    monkeypatch.setattr(photo_service, "extract_text", lambda _path, _engine=None: text)


def _classification_model():
    return {
        "add": [
            {
                "source_text": "Finish biology notes by Friday",
                "title": "Finish biology notes",
                "category": "study",
                "priority": 99,
                "deadline": "not-a-date",
                "suggested_time": "16:30",
                "estimated_minutes": 45,
                "reason": "School deadline",
            },
            {
                "source_text": "Pay electricity bill tomorrow",
                "title": "Pay electricity bill",
                "category": "not-a-category",
                "priority": 2,
                "deadline": None,
                "estimated_minutes": 10,
                "reason": "Money owed",
            },
        ],
        "ignore": [
            {"text": "TODAY'S LIST", "reason": "Heading"},
            {"text": "Call dentist Monday 4pm", "reason": "Appointment note"},
            {"text": "Buy milk and bread", "reason": "Shopping note"},
            {"text": "Doodles and page 1", "reason": "Doodle and page number"},
        ],
    }


def test_model_classifies_ocr_lines_and_python_validates_fields(monkeypatch):
    _fake_ocr(monkeypatch)
    monkeypatch.setattr(llm_service, "available", lambda: True)
    monkeypatch.setattr(llm_service, "model_name", lambda: "mock-photo-ai")

    def fake_complete(system, user):
        assert "Classify" in system
        assert "OCR TEXT" in user
        return _classification_model()

    monkeypatch.setattr(llm_service, "complete_json", fake_complete)

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")

    assert result["ocr_available"] is True
    assert result["ocr_engine"] == "RapidOCR"
    assert result["engine"] == "model: mock-photo-ai"
    assert result["requires_confirmation"] is True
    assert [p["title"] for p in result["proposals"]] == [
        "Finish biology notes",
        "Pay electricity bill",
    ]
    assert result["proposals"][0]["priority"] in (1, 2, 3, 4, 5)
    assert result["proposals"][0]["priority"] != 99
    assert result["proposals"][0]["deadline"] != "not-a-date"
    assert result["proposals"][0]["suggested_time"] == "16:30"
    assert result["proposals"][1]["category"] == "bill"
    assert result["classification"]["add"][0]["reason"] == "School deadline"
    assert result["classification"]["ignore"][0]["reason"] == "Heading"
    assert task_service.list_tasks() == [], "OCR must never write tasks"


def test_rules_fallback_without_a_configured_model(monkeypatch):
    _fake_ocr(monkeypatch)
    monkeypatch.setattr(llm_service, "available", lambda: False)

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")

    assert result["engine"] == "rules"
    assert len(result["proposals"]) == 4
    assert result["proposals"][0]["title"].startswith("Finish biology notes")
    assert "Doodles" not in " ".join(p["title"] for p in result["proposals"])
    assert [x["text"] for x in result["classification"]["ignore"]] == [
        "TODAY'S LIST",
        "Doodles and page 1",
    ]
    assert task_service.list_tasks() == []


def test_model_failure_falls_back_to_rules(monkeypatch):
    _fake_ocr(monkeypatch)
    monkeypatch.setattr(llm_service, "available", lambda: True)
    monkeypatch.setattr(llm_service, "complete_json", lambda _system, _user: None)

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")

    assert result["engine"] == "rules fallback"
    assert len(result["proposals"]) == 4
    assert len(result["classification"]["ignore"]) == 2
    assert task_service.list_tasks() == []


def test_ocr_unavailable_is_reported_honestly(monkeypatch):
    monkeypatch.setattr(photo_service, "selected_engine", lambda: None)
    monkeypatch.setattr(photo_service, "ocr_available", lambda: False)

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")

    assert result["ocr_available"] is False
    assert result["ocr_engine"] is None
    assert result["engine"] == "none"
    assert result["proposals"] == []
    assert result["classification"]["add"] == []
    assert result["classification"]["ignore"] == []
    assert result["requires_confirmation"] is False
    assert "pip install -r requirements.txt" in result["reply"]
    assert task_service.list_tasks() == []


def test_photo_endpoint_and_confirmation_are_approval_first(monkeypatch):
    _fake_ocr(monkeypatch, "Buy milk\nCall dentist Monday 4pm")
    monkeypatch.setattr(llm_service, "available", lambda: False)

    response = client.post(
        "/photo/tasks",
        files={"file": ("notes.png", b"fake", "image/png")},
    )
    assert response.status_code == 200
    proposal_data = response.json()
    assert proposal_data["requires_confirmation"] is True
    assert proposal_data["ocr_engine"] == "RapidOCR"
    assert len(proposal_data["proposals"]) == 2
    assert len(proposal_data["classification"]["add"]) == 2
    assert proposal_data["ignored_lines"] == []
    assert task_service.list_tasks() == []

    unapproved = client.post(
        "/photo/tasks/confirm",
        json={"approved": False, "proposals": proposal_data["proposals"]},
    )
    assert unapproved.json()["saved_count"] == 0
    assert task_service.list_tasks() == []

    approved = client.post(
        "/photo/tasks/confirm",
        json={"approved": True, "proposals": proposal_data["proposals"]},
    )
    assert approved.json()["saved_count"] == 2
    assert len(task_service.list_tasks()) == 2


def test_health_reports_photo_ocr_status(monkeypatch):
    monkeypatch.setattr(photo_service, "selected_engine", lambda: "rapidocr")
    data = client.get("/health").json()
    assert data["photo_ocr"]["available"] is True
    assert data["photo_ocr"]["engine"] == "RapidOCR"


def test_ui_exposes_photo_upload_and_chat_save_controls():
    html = render_ui()
    assert 'id="photoInput"' in html
    assert "uploadPhoto()" in html
    assert "renderPhotoChat" in html
    assert "savePhotoChat" in html
    assert "bubbleHtml" in html
    assert "photo-chat" in html
    assert "Add these" in html
    assert "Ignore these" in html
    assert "Add selected tasks" in html
    assert "/photo/tasks" in html
    assert "/photo/tasks/confirm" in html
    assert "pip install -r requirements.txt" in html
    assert 'id="photoPanel"' not in html


def test_rapidocr_is_the_default_pip_only_engine(monkeypatch):
    monkeypatch.delenv("LIFEPILOT_OCR_ENGINE", raising=False)
    monkeypatch.setattr(photo_service, "_rapidocr_available", lambda: True)
    monkeypatch.setattr(photo_service, "_rapidocr_engine", lambda: _FakeRapidOCR())
    monkeypatch.setattr(photo_service, "_tesseract_available", lambda: True)

    assert photo_service.selected_engine() == "rapidocr"
    assert photo_service.status()["engine"] == "RapidOCR"
    assert photo_service.ocr_available() is True


def test_rapidocr_reads_text_without_a_tesseract_binary(monkeypatch):
    monkeypatch.setattr(photo_service, "_rapidocr_engine", lambda: _FakeRapidOCR())
    monkeypatch.setattr(photo_service, "_tesseract_available", lambda: False)

    text = photo_service.extract_text("unused.png", "rapidocr")

    assert text == "Buy milk\nCall dentist Monday 4pm"


def test_ocr_engine_can_be_forced_or_disabled(monkeypatch):
    monkeypatch.setattr(photo_service, "_rapidocr_available", lambda: True)
    monkeypatch.setattr(photo_service, "_rapidocr_engine", lambda: _FakeRapidOCR())
    monkeypatch.setattr(photo_service, "_tesseract_available", lambda: True)

    monkeypatch.setenv("LIFEPILOT_OCR_ENGINE", "tesseract")
    assert photo_service.selected_engine() == "tesseract"
    assert photo_service.status()["engine"] == "Tesseract"

    monkeypatch.setenv("LIFEPILOT_OCR_ENGINE", "none")
    assert photo_service.selected_engine() is None
    assert photo_service.status()["available"] is False


def test_legacy_rapidocr_tuple_output_is_supported():
    legacy = ([[None, "Buy milk", 0.99], [None, "Call dentist", 0.97]], 0.12)
    assert photo_service._rapidocr_lines(legacy) == ["Buy milk", "Call dentist"]


def test_photo_classification_marks_headings_and_doodles_as_ignored(monkeypatch):
    _fake_ocr(monkeypatch)
    monkeypatch.setattr(llm_service, "available", lambda: False)

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")
    ignored = result["classification"]["ignore"]

    assert [item["text"] for item in ignored] == [
        "TODAY'S LIST",
        "Doodles and page 1",
    ]
    assert all(item["reason"] for item in ignored)
    assert all("Doodles" not in item["title"] for item in result["proposals"])


def test_model_classification_reasons_are_exposed(monkeypatch):
    _fake_ocr(monkeypatch)
    monkeypatch.setattr(llm_service, "available", lambda: True)
    monkeypatch.setattr(llm_service, "model_name", lambda: "mock-photo-ai")
    monkeypatch.setattr(llm_service, "complete_json", lambda _system, _user: _classification_model())

    result = photo_service.extract_tasks_from_photo(b"fake", "notes.png")
    add = result["classification"]["add"]
    ignore = result["classification"]["ignore"]

    assert [item["reason"] for item in add] == ["School deadline", "Money owed"]
    assert ignore[0]["reason"] == "Heading"
    assert ignore[-1]["reason"] == "Doodle and page number"
    assert all("reason" not in proposal for proposal in result["proposals"])


def test_ui_is_emoji_free_and_quick_add_has_no_effort():
    html = render_ui()

    assert EMOJI.search(html) is None
    assert 'id="ed_minutes"' not in html
    assert ">Effort<" not in html
    assert "My tasks" in html
    assert "focusTasks()" in html
    assert 'aria-label="Delete task"' in html
    assert ">Delete</button>" in html

def test_delete_task_endpoint_requires_approval_and_removes_task():
    created = client.post(
        "/tasks",
        json={"title": "Temporary task", "approved": True},
    ).json()

    unapproved = client.delete(f"/tasks/{created['id']}")
    assert unapproved.status_code == 400
    assert len(task_service.list_tasks()) == 1

    approved = client.delete(f"/tasks/{created['id']}?approved=true")
    assert approved.status_code == 200
    assert approved.json()["deleted"] == created["id"]
    assert task_service.list_tasks() == []
