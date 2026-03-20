from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ..app.config import Settings
from ..app.main import create_app
from ..app.services.extract import ExtractionResult, ExtractionServiceError


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class StubExtractor:
    def __init__(
        self,
        result: ExtractionResult | None = None,
        llm_result: ExtractionResult | None = None,
        error: Exception | None = None,
        llm_error: Exception | None = None,
    ) -> None:
        self.result = result or ExtractionResult(items=[], extractor="heuristic")
        self.llm_result = llm_result or ExtractionResult(items=[], extractor="llm")
        self.error = error
        self.llm_error = llm_error

    def extract(self, text: str) -> ExtractionResult:
        if self.error is not None:
            raise self.error
        return self.result

    def extract_llm(self, text: str) -> ExtractionResult:
        if self.llm_error is not None:
            raise self.llm_error
        return self.llm_result


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        app_name="Action Item Extractor Test",
        frontend_dir=FRONTEND_DIR,
        data_dir=tmp_path,
        database_path=tmp_path / "test.db",
        ollama_model="test-model",
        allow_llm_fallback=True,
    )
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def test_create_and_list_notes(client: TestClient) -> None:
    create_response = client.post("/notes", json={"content": "  Review architecture  "})
    assert create_response.status_code == 201
    created_note = create_response.json()
    assert created_note["content"] == "Review architecture"

    list_response = client.get("/notes")
    assert list_response.status_code == 200
    notes = list_response.json()
    assert len(notes) == 1
    assert notes[0]["id"] == created_note["id"]
    assert notes[0]["content"] == "Review architecture"


def test_extract_action_items_persists_note_and_items(client: TestClient) -> None:
    client.app.state.action_item_extractor = StubExtractor(
        result=ExtractionResult(
            items=["Write API tests", "Refactor database layer"],
            extractor="heuristic",
        )
    )

    response = client.post(
        "/action-items/extract",
        json={"text": "Meeting follow-ups", "save_note": True},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["extractor"] == "heuristic"
    assert payload["note_id"] == 1
    assert [item["text"] for item in payload["items"]] == [
        "Write API tests",
        "Refactor database layer",
    ]
    assert all(item["note_id"] == 1 for item in payload["items"])
    assert all(item["done"] is False for item in payload["items"])

    list_response = client.get("/action-items", params={"note_id": 1})
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 2


def test_extract_llm_persists_note_and_items(client: TestClient) -> None:
    client.app.state.action_item_extractor = StubExtractor(
        llm_result=ExtractionResult(
            items=["Draft the design doc", "Share notes with the team"],
            extractor="llm",
        )
    )

    response = client.post(
        "/action-items/extract-llm",
        json={"text": "Planning session follow-ups", "save_note": True},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["extractor"] == "llm"
    assert payload["note_id"] == 1
    assert [item["text"] for item in payload["items"]] == [
        "Draft the design doc",
        "Share notes with the team",
    ]

    notes_response = client.get("/notes")
    assert notes_response.status_code == 200
    notes = notes_response.json()
    assert len(notes) == 1
    assert notes[0]["content"] == "Planning session follow-ups"


def test_mark_done_returns_not_found_for_missing_item(client: TestClient) -> None:
    response = client.post("/action-items/999/done", json={"done": True})
    assert response.status_code == 404
    assert response.json() == {
        "detail": "action item not found",
        "error_code": "not_found",
    }


def test_extract_validation_errors_use_shared_error_shape(client: TestClient) -> None:
    response = client.post("/action-items/extract", json={"text": "   ", "save_note": True})
    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"] == "text is required"
    assert payload["error_code"] == "validation_error"
    assert payload["errors"]


def test_extract_returns_service_unavailable_when_extractor_fails(
    client: TestClient,
) -> None:
    client.app.state.action_item_extractor = StubExtractor(
        error=ExtractionServiceError("service unavailable")
    )

    response = client.post(
        "/action-items/extract",
        json={"text": "Need action items", "save_note": False},
    )
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Action item extraction is currently unavailable",
        "error_code": "service_unavailable",
    }


def test_extract_llm_returns_service_unavailable_when_extractor_fails(
    client: TestClient,
) -> None:
    client.app.state.action_item_extractor = StubExtractor(
        llm_error=ExtractionServiceError("service unavailable")
    )

    response = client.post(
        "/action-items/extract-llm",
        json={"text": "Need action items", "save_note": False},
    )
    assert response.status_code == 503
    assert response.json() == {
        "detail": "LLM action item extraction is currently unavailable",
        "error_code": "service_unavailable",
    }
