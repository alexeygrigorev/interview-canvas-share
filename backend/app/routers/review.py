"""Historical audit routes."""

from fastapi import APIRouter, Depends

from ..models import AuditEvent, InterviewSession, User
from ..store import DatabaseStore
from .dependencies import require_session_manager

router = APIRouter(prefix="/v1/sessions", tags=["Review"])


@router.get("/{id}/audit", response_model=list[AuditEvent], operation_id="getAudit")
def get_audit(
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> list[AuditEvent]:
    session, _, store = context
    return store.list_audit(session.id)
