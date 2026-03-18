from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, validator


class NoteCreateRequest(BaseModel):
    content: str

    @validator("content")
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("content is required")
        return normalized


class NoteResponse(BaseModel):
    id: int
    content: str
    created_at: str


class ActionItemExtractRequest(BaseModel):
    text: str
    save_note: bool = False

    @validator("text")
    def validate_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text is required")
        return normalized


class ActionItemResponse(BaseModel):
    id: int
    note_id: Optional[int]
    text: str
    done: bool
    created_at: str


class ActionItemDoneRequest(BaseModel):
    done: bool = True


class ActionItemExtractResponse(BaseModel):
    note_id: Optional[int]
    extractor: str
    items: list[ActionItemResponse]
