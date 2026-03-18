from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status

from ..db import Database, NoteRecord
from ..dependencies import get_database
from ..errors import COMMON_ERROR_RESPONSES, NotFoundError
from ..schemas import NoteCreateRequest, NoteResponse


router = APIRouter(prefix="/notes", tags=["notes"])


def _serialize_note(note: NoteRecord) -> NoteResponse:
    return NoteResponse(id=note.id, content=note.content, created_at=note.created_at)


@router.post(
    "",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERROR_RESPONSES,
)
def create_note(
    payload: NoteCreateRequest, database: Database = Depends(get_database)
) -> NoteResponse:
    note = database.create_note(payload.content)
    return _serialize_note(note)


@router.get("", response_model=list[NoteResponse], responses=COMMON_ERROR_RESPONSES)
def list_notes(database: Database = Depends(get_database)) -> list[NoteResponse]:
    return [_serialize_note(note) for note in database.list_notes()]


@router.get(
    "/{note_id}",
    response_model=NoteResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def get_single_note(
    note_id: int = Path(..., ge=1),
    database: Database = Depends(get_database),
) -> NoteResponse:
    note = database.get_note(note_id)
    if note is None:
        raise NotFoundError("note not found")
    return _serialize_note(note)
