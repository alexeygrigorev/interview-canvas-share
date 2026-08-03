"""Session lifecycle, settings, and guest-link routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from ..auth import Principal, get_current_user
from ..errors import conflict, not_found
from ..models import (
    CreateGuestLinkRequest,
    CreateSessionRequest,
    GuestLink,
    InterviewSession,
    PermissionChangedMessage,
    SessionDetail,
    SessionEndedMessage,
    SessionListItem,
    TrueResponse,
    UpdateSessionRequest,
    User,
)
from ..store import DatabaseStore, get_store
from .dependencies import require_session_for_principal, require_session_manager
from .realtime import broadcast_message

router = APIRouter(prefix="/v1/sessions", tags=["Sessions"])


@router.get("", response_model=list[SessionListItem], operation_id="listSessions")
def list_sessions(
    current_user: User = Depends(get_current_user),
    store: DatabaseStore = Depends(get_store),
) -> list[SessionListItem]:
    return store.list_sessions_for_user(current_user.id)


@router.post(
    "",
    response_model=InterviewSession,
    status_code=status.HTTP_201_CREATED,
    operation_id="createSession",
)
def create_session(
    payload: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    store: DatabaseStore = Depends(get_store),
) -> InterviewSession:
    return store.create_session(
        owner_user_id=current_user.id,
        title=payload.title,
        prompt=payload.prompt,
        duration_minutes=payload.duration_minutes,
        scheduled_at=payload.scheduled_at,
    )


def _transition(
    id: str,
    target: str,
    allowed: set[str],
    session: InterviewSession,
    current_user: User,
    store: DatabaseStore,
) -> InterviewSession:
    if session.state not in allowed:
        raise conflict(
            "invalid_session_state",
            f"A {session.state} interview cannot transition to {target}.",
        )
    updated = store.transition_session(id, target, current_user.id)
    if updated is None:
        raise not_found("session_not_found", "This interview does not exist.")
    return updated


# Keep the static lifecycle routes before /{id}; otherwise Starlette can match
# the dynamic route first and return a 405 for a valid POST /start-style path.
@router.post("/{id}/start", response_model=InterviewSession, operation_id="startSession")
async def start_session(
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> InterviewSession:
    session, current_user, store = context
    updated = _transition(session.id, "live", {"draft"}, session, current_user, store)
    await broadcast_message(
        session.id,
        PermissionChangedMessage(type="permission_changed", sessionId=session.id, session=updated),
    )
    return updated


@router.post("/{id}/end", response_model=InterviewSession, operation_id="endSession")
async def end_session(
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> InterviewSession:
    session, current_user, store = context
    updated = _transition(session.id, "ended", {"live"}, session, current_user, store)
    await broadcast_message(
        session.id,
        SessionEndedMessage(type="session_ended", sessionId=session.id),
    )
    return updated


@router.post("/{id}/archive", response_model=InterviewSession, operation_id="archiveSession")
async def archive_session(
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> InterviewSession:
    session, current_user, store = context
    updated = _transition(session.id, "archived", {"ended"}, session, current_user, store)
    await broadcast_message(
        session.id,
        PermissionChangedMessage(type="permission_changed", sessionId=session.id, session=updated),
    )
    return updated


@router.post("/{id}/duplicate", response_model=InterviewSession, operation_id="duplicateSession")
def duplicate_session(
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> InterviewSession:
    session, current_user, store = context
    copy = store.duplicate_session(session.id, current_user.id)
    if copy is None:
        raise not_found("session_not_found", "This interview does not exist.")
    return copy


@router.post(
    "/{id}/guest-links",
    response_model=GuestLink,
    status_code=status.HTTP_201_CREATED,
    operation_id="createGuestLink",
    tags=["Guest access"],
)
def create_guest_link(
    payload: CreateGuestLinkRequest | None = None,
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> GuestLink:
    session, current_user, store = context
    if session.state == "archived":
        raise conflict("invalid_session_state", "Archived interviews cannot receive guest links.")
    role = payload.role_granted if payload is not None else "candidate"
    link, _ = store.create_guest_link(session.id, role, current_user.id)
    return link


@router.delete(
    "/{id}/guest-links/{linkId}",
    response_model=TrueResponse,
    operation_id="revokeGuestLink",
    tags=["Guest access"],
)
def revoke_guest_link(
    linkId: str,
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> bool:
    session, current_user, store = context
    revoked = store.revoke_guest_link(session.id, linkId, current_user.id)
    if revoked is None:
        raise not_found("link_not_found", "This guest link does not exist.")
    return True


@router.get("/{id}", response_model=SessionDetail, operation_id="getSession")
def get_session(
    context: tuple[InterviewSession, Principal, DatabaseStore] = Depends(require_session_for_principal),
) -> SessionDetail:
    session, _, store = context
    detail = store.session_detail(session.id)
    if detail is None:
        raise not_found("session_not_found", "This interview does not exist.")
    return detail


@router.patch("/{id}", response_model=InterviewSession, operation_id="updateSession")
async def update_session(
    payload: UpdateSessionRequest,
    context: tuple[InterviewSession, User, DatabaseStore] = Depends(require_session_manager),
) -> InterviewSession:
    session, current_user, store = context
    changes = payload.model_dump(exclude_unset=True)
    updated = store.update_session(session.id, changes, current_user.id)
    if updated is None:
        raise not_found("session_not_found", "This interview does not exist.")
    await broadcast_message(
        session.id,
        PermissionChangedMessage(type="permission_changed", sessionId=session.id, session=updated),
    )
    return updated
