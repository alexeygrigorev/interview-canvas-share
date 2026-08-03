"""Development login endpoint for obtaining the contract's bearer token."""

from fastapi import APIRouter, Depends

from ..auth import authenticate_user, create_access_token
from ..errors import ApiException
from ..models import LoginRequest, TokenResponse
from ..store import InMemoryStore, get_store

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse, operation_id="login")
def login(payload: LoginRequest, store: InMemoryStore = Depends(get_store)) -> TokenResponse:
    user = authenticate_user(str(payload.email), payload.password, store)
    if user is None:
        raise ApiException(401, "invalid_credentials", "Email or password is incorrect.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        token_type="bearer",
        user=user,
    )
