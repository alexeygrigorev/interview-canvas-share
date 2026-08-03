"""Password hashing, JWT bearer tokens, and principal dependencies."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import Depends
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash

from .errors import invalid_token, unauthorized
from .models import Participant, User
from .store import GUEST_COOKIE_NAME, InMemoryStore, get_store

JWT_ALGORITHM = "HS256"
JWT_SECRET = os.getenv("SDIP_JWT_SECRET", "local-development-secret-change-me")
ACCESS_TOKEN_MINUTES = int(os.getenv("SDIP_ACCESS_TOKEN_MINUTES", "60"))

password_hasher = PasswordHash.recommended()
bearer_scheme = HTTPBearer(scheme_name="bearerAuth", auto_error=False)
guest_cookie_scheme = APIKeyCookie(
    name=GUEST_COOKIE_NAME,
    scheme_name="guestSession",
    auto_error=False,
)


@dataclass(frozen=True, slots=True)
class Principal:
    kind: Literal["user", "guest"]
    user: User | None = None
    participant: Participant | None = None

    @property
    def user_id(self) -> str | None:
        return self.user.id if self.user else None

    @property
    def participant_id(self) -> str | None:
        return self.participant.id if self.participant else None


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_MINUTES))
    payload = {"sub": user_id, "iat": now, "exp": expires, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as exc:
        raise invalid_token() from exc
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise invalid_token()
    return user_id


def authenticate_bearer(token: str, store: InMemoryStore) -> Principal:
    user_id = decode_access_token(token)
    user_record = store.get_user(user_id)
    if user_record is None:
        raise invalid_token("The access token refers to an unknown user.")
    return Principal(kind="user", user=user_record.public())


def authenticate_user(email: str, password: str, store: InMemoryStore) -> User | None:
    user_record = store.find_user_by_email(email)
    if user_record is None or not verify_password(password, user_record.password_hash):
        return None
    return user_record.public()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    store: InMemoryStore = Depends(get_store),
) -> User:
    if credentials is None:
        raise unauthorized()
    principal = authenticate_bearer(credentials.credentials, store)
    assert principal.user is not None
    return principal.user


def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    guest_cookie: str | None = Depends(guest_cookie_scheme),
    store: InMemoryStore = Depends(get_store),
) -> Principal:
    # A supplied bearer token takes precedence over a cookie. This avoids
    # silently downgrading an invalid bearer credential to guest access.
    if credentials is not None:
        return authenticate_bearer(credentials.credentials, store)
    if guest_cookie:
        participant = store.resolve_guest_cookie(guest_cookie)
        if participant is not None:
            return Principal(kind="guest", participant=participant)
        raise unauthorized("The guest session is invalid or has expired.")
    raise unauthorized()


def authenticate_websocket(
    authorization: str | None,
    guest_cookie: str | None,
    store: InMemoryStore,
) -> Principal:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.casefold() != "bearer" or not token:
            raise unauthorized("The Authorization header must use the Bearer scheme.")
        return authenticate_bearer(token, store)
    if guest_cookie:
        participant = store.resolve_guest_cookie(guest_cookie)
        if participant:
            return Principal(kind="guest", participant=participant)
        raise unauthorized("The guest session is invalid or has expired.")
    raise unauthorized()
