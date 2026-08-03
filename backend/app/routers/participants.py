"""Session participant membership and leave/remove operations."""

from fastapi import APIRouter, Depends

from ..auth import Principal, get_current_user
from ..errors import forbidden, not_found
from ..models import Participant, PresenceLeaveMessage, PresenceUpdateMessage, TrueResponse, User
from ..store import DatabaseStore, get_store
from .dependencies import require_session_for_principal
from .realtime import broadcast_message

router = APIRouter(prefix="/v1/sessions", tags=["Participants"])


@router.post("/{id}/participants", response_model=Participant, operation_id="joinAsOwner")
async def join_as_owner(
    id: str,
    current_user: User = Depends(get_current_user),
    store: DatabaseStore = Depends(get_store),
) -> Participant:
    participant = store.join_authenticated_participant(id, current_user.id)
    await broadcast_message(
        id,
        PresenceUpdateMessage(type="presence_update", sessionId=id, participant=participant),
    )
    return participant


@router.delete("/{id}/participants/{pid}", response_model=TrueResponse, operation_id="removeParticipant")
async def remove_participant(
    pid: str,
    context: tuple[object, Principal, DatabaseStore] = Depends(require_session_for_principal),
) -> bool:
    session, principal, store = context
    target = store.get_participant(session.id, pid)
    if target is None:
        raise not_found("participant_not_found", "This participant does not exist in the interview.")

    is_self = (
        principal.participant_id == target.id
        or (principal.user_id is not None and target.user_id == principal.user_id)
    )
    can_remove = principal.user_id is not None and store.user_can_manage(session.id, principal.user_id)
    if not is_self and not can_remove:
        raise forbidden("Only the participant or an interviewer can remove this participant.")

    actor = principal.user_id or principal.participant_id or "unknown"
    removed = store.leave_participant(session.id, target.id, actor)
    if removed is None:
        raise not_found("participant_not_found", "This participant does not exist in the interview.")
    await broadcast_message(
        session.id,
        PresenceLeaveMessage(
            type="presence_leave",
            sessionId=session.id,
            participantId=target.id,
        ),
    )
    return True
