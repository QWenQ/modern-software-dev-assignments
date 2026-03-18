from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query, status

from ..db import ActionItemRecord, Database
from ..dependencies import get_action_item_extractor, get_database
from ..errors import COMMON_ERROR_RESPONSES, NotFoundError, ServiceError
from ..schemas import (
    ActionItemDoneRequest,
    ActionItemExtractRequest,
    ActionItemExtractResponse,
    ActionItemResponse,
)
from ..services.extract import ActionItemExtractor, ExtractionServiceError


router = APIRouter(prefix="/action-items", tags=["action-items"])


def _serialize_action_item(item: ActionItemRecord) -> ActionItemResponse:
    return ActionItemResponse(
        id=item.id,
        note_id=item.note_id,
        text=item.text,
        done=item.done,
        created_at=item.created_at,
    )


@router.post(
    "/extract",
    response_model=ActionItemExtractResponse,
    status_code=status.HTTP_201_CREATED,
    responses=COMMON_ERROR_RESPONSES,
)
def extract(
    payload: ActionItemExtractRequest,
    database: Database = Depends(get_database),
    extractor: ActionItemExtractor = Depends(get_action_item_extractor),
) -> ActionItemExtractResponse:
    try:
        extraction = extractor.extract(payload.text)
    except ExtractionServiceError as exc:
        raise ServiceError("Action item extraction is currently unavailable") from exc

    note_id: Optional[int] = None
    if payload.save_note:
        note, items = database.create_note_with_action_items(
            payload.text, extraction.items
        )
        note_id = note.id
    else:
        items = database.create_action_items(extraction.items, note_id=None)

    return ActionItemExtractResponse(
        note_id=note_id,
        extractor=extraction.extractor,
        items=[_serialize_action_item(item) for item in items],
    )


@router.get(
    "",
    response_model=list[ActionItemResponse],
    responses=COMMON_ERROR_RESPONSES,
)
def list_all(
    note_id: Optional[int] = Query(default=None, ge=1),
    database: Database = Depends(get_database),
) -> list[ActionItemResponse]:
    rows = database.list_action_items(note_id=note_id)
    return [_serialize_action_item(row) for row in rows]


@router.post(
    "/{action_item_id}/done",
    response_model=ActionItemResponse,
    responses=COMMON_ERROR_RESPONSES,
)
def mark_done(
    payload: ActionItemDoneRequest,
    action_item_id: int = Path(..., ge=1),
    database: Database = Depends(get_database),
) -> ActionItemResponse:
    action_item = database.set_action_item_done(action_item_id, payload.done)
    if action_item is None:
        raise NotFoundError("action item not found")
    return _serialize_action_item(action_item)
