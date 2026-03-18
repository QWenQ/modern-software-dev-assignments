import os
import pytest

from ..app.services.extract import extract_action_items, extract_action_items_llm


def test_extract_bullets_and_checkboxes():
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
    """Unit tests for extract_action_items_llm() function."""
    
    def test_extract_bullet_lists(self):
        """Test extraction from bullet list format."""
        text = """
        Project tasks:
        - Set up database schema
        * Create API endpoints
        • Write documentation
        """.strip()
        
        items = extract_action_items_llm(text)
        assert len(items) > 0
        # Check that at least some expected items are extracted
        items_lower = [item.lower() for item in items]
        assert any("database" in item for item in items_lower)
        assert any("api" in item or "endpoint" in item for item in items_lower)
    
    def test_extract_keyword_prefixed_lines(self):
        """Test extraction from lines with action keywords."""
        text = """
        todo: Fix the login bug
        action: Review pull request
        next: Deploy to production
        """.strip()
        
        items = extract_action_items_llm(text)
        assert len(items) > 0
        items_lower = [item.lower() for item in items]
        # Verify that action-related content is extracted
        assert any("fix" in item or "login" in item or "bug" in item for item in items_lower)
        assert any("review" in item or "pull" in item for item in items_lower)
        assert any("deploy" in item or "production" in item for item in items_lower)
    
    def test_extract_with_checkboxes(self):
        """Test extraction from checkbox format."""
        text = """
        Meeting notes:
        [ ] Complete project proposal
        [ ] Schedule follow-up meeting
        [x] Send initial email
        """.strip()
        
        items = extract_action_items_llm(text)
        assert len(items) > 0
        items_lower = [item.lower() for item in items]
        # Should extract unchecked items
        assert any("proposal" in item or "complete" in item for item in items_lower)
        assert any("meeting" in item or "schedule" in item for item in items_lower)
    
    def test_empty_input(self):
        """Test with empty input."""
        text = ""
        items = extract_action_items_llm(text)
        assert isinstance(items, list)
        assert len(items) == 0
    
    def test_no_action_items(self):
        """Test with text that contains no action items."""
        text = "This is just a narrative paragraph with no specific tasks mentioned."
        items = extract_action_items_llm(text)
        assert isinstance(items, list)
    
    def test_deduplication(self):
        """Test that duplicate items are removed."""
        text = """
        - Fix the bug
        - Fix the bug
        * Fix the bug
        """.strip()
        
        items = extract_action_items_llm(text)
        # Should have only one item after deduplication
        items_lower = [item.lower() for item in items]
        fix_bug_count = sum(1 for item in items_lower if "fix" in item and "bug" in item)
        assert fix_bug_count <= 1
    
    def test_mixed_format_input(self):
        """Test with mixed format input."""
        text = """
        Meeting summary:
        - Prepare presentation slides
        todo: Review feedback
        * [ ] Update documentation
        next: Schedule demo meeting
        """.strip()
        
        items = extract_action_items_llm(text)
        assert len(items) > 0
        items_lower = [item.lower() for item in items]
        # Should extract various items in different formats
        assert any("present" in item or "slide" in item for item in items_lower)
        assert any("review" in item or "feedback" in item for item in items_lower)
