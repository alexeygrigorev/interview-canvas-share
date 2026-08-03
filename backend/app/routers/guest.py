"""Public guest-link inspection and joining."""

from fastapi import APIRouter, Depends, Response

from ..models import JoinRequest, JoinResponse, TokenInspection
from ..store import GUEST_COOKIE_NAME, GUEST_SESSION_TTL, InMemoryStore, get_store

router = APIRouter(prefix="/v1/join", tags=["Guest access"])


@router.get("/{token}", response_model=TokenInspection, operation_id="inspectToken")
def inspect_token(token: str, store: InMemoryStore = Depends(get_store)) -> TokenInspection:
    return store.inspect_guest_token(token)


@router.post("/{token}", response_model=JoinResponse, operation_id="joinGuest")
def join_guest(
    token: str,
    payload: JoinRequest,
    response: Response,
    store: InMemoryStore = Depends(get_store),
) -> JoinResponse:
    result = store.join_guest(token, payload.display_name)
    response.set_cookie(
        key=GUEST_COOKIE_NAME,
        value=result.cookie_value,
        max_age=int(GUEST_SESSION_TTL.total_seconds()),
        httponly=True,
        samesite="lax",
        path="/",
    )
    return JoinResponse(participant=result.participant, session=result.session)
