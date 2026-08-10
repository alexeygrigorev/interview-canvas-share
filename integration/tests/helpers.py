"""Constants and helpers shared by the integration tests."""

from __future__ import annotations

import json
import os
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from websockets.sync.client import ClientConnection, connect

DEFAULT_PORT = os.getenv("APP_PORT", "8100")
BASE_URL = os.getenv("SDIP_BASE_URL", f"http://localhost:{DEFAULT_PORT}").rstrip("/")

# The stack is usually started moments before the suite runs, and the app only
# answers once it has created its tables and seeded the database.
STARTUP_TIMEOUT = float(os.getenv("SDIP_STARTUP_TIMEOUT", "180"))

# Seeded demo interviewer - see the seed data in `backend/app/store.py`.
INTERVIEWER = {"email": "avery@northwind.dev", "password": "demo-password"}

GUEST_COOKIE_NAME = "sdip_guest_session"


def unique(prefix: str) -> str:
    """A per-test marker, so runs never collide with each other or the seed."""

    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def node_element(actor: str, label: str, x: float = 120, y: float = 80) -> dict[str, Any]:
    """A minimal canvas node, shaped like the ones the frontend sends."""

    now = "2026-01-01T00:00:00Z"
    return {
        "id": unique("el_").replace("-", ""),
        "kind": "node",
        "componentType": "cache",
        "x": x,
        "y": y,
        "width": 168,
        "height": 76,
        "label": label,
        "created_by": actor,
        "created_at": now,
        "updated_at": now,
    }


@contextmanager
def room(
    base_url: str,
    session_id: str,
    *,
    token: str | None = None,
    cookie: str | None = None,
) -> Iterator[ClientConnection]:
    """Open the realtime room as an authenticated user or as a guest."""

    url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    headers: dict[str, str] = {}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if cookie is not None:
        headers["Cookie"] = f"{GUEST_COOKIE_NAME}={cookie}"

    with connect(
        f"{url}/v1/sessions/{session_id}/realtime",
        additional_headers=headers,
        subprotocols=["sdip"],
        open_timeout=15,
    ) as connection:
        yield connection


def next_message(
    connection: ClientConnection, type_: str, timeout: float = 15
) -> dict[str, Any]:
    """The next message of `type_`, skipping the others the room fans out."""

    deadline = time.monotonic() + timeout
    seen: list[str] = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(f"no {type_} message within {timeout:.0f}s; saw {seen}")
        message = json.loads(connection.recv(timeout=remaining))
        if message.get("type") == type_:
            return message
        seen.append(str(message.get("type") or message))
