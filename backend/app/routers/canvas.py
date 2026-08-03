"""Persisted canvas snapshot routes."""

from datetime import datetime

from fastapi import APIRouter, Depends

from ..auth import Principal
from ..errors import forbidden, not_found
from ..models import CanvasDocument, DocumentUpdateMessage, SaveCanvasRequest
from ..store import DatabaseStore
from .dependencies import require_session_for_principal
from .realtime import broadcast_message

router = APIRouter(prefix="/v1/sessions", tags=["Canvas"])


@router.get("/{id}/canvas", response_model=CanvasDocument, operation_id="getCanvas")
def get_canvas(
    context: tuple[object, Principal, DatabaseStore] = Depends(require_session_for_principal),
) -> CanvasDocument:
    session, _, store = context
    canvas = store.get_canvas(session.id)
    if canvas is None:
        raise not_found("canvas_not_found", "Canvas unavailable.")
    return canvas


@router.put("/{id}/canvas", response_model=datetime, operation_id="saveCanvas")
async def save_canvas(
    payload: SaveCanvasRequest,
    context: tuple[object, Principal, DatabaseStore] = Depends(require_session_for_principal),
) -> datetime:
    session, principal, store = context
    if not store.principal_can_edit(
        session.id,
        user_id=principal.user_id,
        participant_id=principal.participant_id,
    ):
        raise forbidden("This canvas is read-only for your role or the current session state.")
    if principal.kind == "guest" and payload.actor != principal.participant_id:
        raise forbidden("The canvas actor must be the current guest participant.")
    updated_at = store.save_canvas(session.id, payload.elements, payload.actor)
    if updated_at is None:
        raise not_found("canvas_not_found", "Canvas unavailable.")
    await broadcast_message(
        session.id,
        DocumentUpdateMessage(
            type="document_update",
            sessionId=session.id,
            elements=payload.elements,
            actor=payload.actor,
        ),
    )
    return updated_at
