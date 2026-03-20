from __future__ import annotations

import pytest

from ..app.services import extract as extract_service
from ..app.services.extract import (
    ExtractionServiceError,
    extract_action_items,
    extract_action_items_llm,
)


def test_extract_bullets_and_checkboxes() -> None:
    text = """
    Notes from meeting:
    - [ ] Set up database
    * implement API extract endpoint
    1. Write tests
    Some narrative sentence.
    """.strip()

    items = extract_action_items(text)
    assert "Set up database" in items
    assert "implement API extract endpoint" in items
    assert "Write tests" in items


class TestExtractActionItemsLLM:
    @staticmethod
    def _mock_ollama(monkeypatch: pytest.MonkeyPatch, response_text: str) -> None:
        monkeypatch.setattr(
            extract_service,
            "_call_ollama",
            lambda prompt, model_name: response_text,
        )

    def test_extract_bullet_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(
            monkeypatch,
            '["Set up database schema", "Create API endpoints", "Write documentation"]',
        )

        text = """
        Project tasks:
        - Set up database schema
        * Create API endpoints
        • Write documentation
        """.strip()

        items = extract_action_items_llm(text)
        assert items == [
            "Set up database schema",
            "Create API endpoints",
            "Write documentation",
        ]

    def test_extract_keyword_prefixed_lines(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(
            monkeypatch,
            '["Fix the login bug", "Review pull request", "Deploy to production"]',
        )

        text = """
        todo: Fix the login bug
        action: Review pull request
        next: Deploy to production
        """.strip()

        items = extract_action_items_llm(text)
        assert items == [
            "Fix the login bug",
            "Review pull request",
            "Deploy to production",
        ]

    def test_extract_with_checkboxes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(
            monkeypatch,
            '["Complete project proposal", "Schedule follow-up meeting"]',
        )

        text = """
        Meeting notes:
        [ ] Complete project proposal
        [ ] Schedule follow-up meeting
        [x] Send initial email
        """.strip()

        items = extract_action_items_llm(text)
        assert items == [
            "Complete project proposal",
            "Schedule follow-up meeting",
        ]

    def test_empty_input(self) -> None:
        items = extract_action_items_llm("")
        assert items == []

    def test_no_action_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(monkeypatch, '[]')

        text = "This is just a narrative paragraph with no specific tasks mentioned."
        items = extract_action_items_llm(text)
        assert items == []

    def test_deduplication(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(
            monkeypatch,
            '["Fix the bug", "Fix the bug", "- Fix the bug"]',
        )

        text = """
        - Fix the bug
        - Fix the bug
        * Fix the bug
        """.strip()

        items = extract_action_items_llm(text)
        assert items == ["Fix the bug"]

    def test_mixed_format_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._mock_ollama(
            monkeypatch,
            '["Prepare presentation slides", "Review feedback", "Update documentation", "Schedule demo meeting"]',
        )

        text = """
        Meeting summary:
        - Prepare presentation slides
        todo: Review feedback
        * [ ] Update documentation
        next: Schedule demo meeting
        """.strip()

        items = extract_action_items_llm(text)
        assert items == [
            "Prepare presentation slides",
            "Review feedback",
            "Update documentation",
            "Schedule demo meeting",
        ]

    def test_falls_back_to_heuristics_when_llm_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def raise_service_error(prompt: str, model_name: str) -> str:
            raise ExtractionServiceError("service unavailable")

        monkeypatch.setattr(extract_service, "_call_ollama", raise_service_error)

        text = """
        - Fix the bug
        - Write tests
        """.strip()

        items = extract_action_items_llm(text)
        assert items == ["Fix the bug", "Write tests"]
