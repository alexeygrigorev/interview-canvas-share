"""Reusable authorization checks for session-scoped routes."""

from __future__ import annotations

from fastapi import Depends

from ..auth import Principal, get_current_user, get_principal
from ..errors import forbidden, not_found
from ..models import InterviewSession, User
from ..store import InMemoryStore, get_store


def require_session_for_principal(
    id: str,
    principal: Principal = Depends(get_principal),
    store: InMemoryStore = Depends(get_store),
) -> tuple[InterviewSession, Principal, InMemoryStore]:
    session = store.get_session(id)
    if session is None:
        raise not_found("session_not_found", "This interview does not exist.")
    if not store.principal_can_access(
        id,
        user_id=principal.user_id,
        participant_id=principal.participant_id,
    ):
        raise forbidden("You are not a participant in this interview.")
    return session, principal, store


def require_session_manager(
    id: str,
    current_user: User = Depends(get_current_user),
    store: InMemoryStore = Depends(get_store),
) -> tuple[InterviewSession, User, InMemoryStore]:
    session = store.get_session(id)
    if session is None:
        raise not_found("session_not_found", "This interview does not exist.")
    if not store.user_can_manage(id, current_user.id):
        raise forbidden("Only an interviewer for this interview can perform this operation.")
    return session, current_user, store
