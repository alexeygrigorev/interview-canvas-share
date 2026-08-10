"""Fixtures for tests that talk to a running deployment over the network.

Unlike `backend/tests`, nothing here imports the application: the suite only
sees what the stack publishes, so it also covers what the unit tests cannot
reach - the built image, the static bundle it serves, PostgreSQL, and the
WebSocket gateway.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from helpers import BASE_URL, GUEST_COOKIE_NAME, INTERVIEWER, STARTUP_TIMEOUT, unique


@pytest.fixture(scope="session")
def base_url() -> str:
    """The stack's base URL, returned only once it answers /health."""

    deadline = time.monotonic() + STARTUP_TIMEOUT
    last_error: object = "no attempt was made"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"{BASE_URL}/health", timeout=5)
            if response.status_code == 200:
                return BASE_URL
            last_error = f"{response.status_code} {response.text}"
        except httpx.HTTPError as error:  # not listening yet
            last_error = error
        time.sleep(1)
    raise pytest.UsageError(
        f"{BASE_URL} did not become healthy within {STARTUP_TIMEOUT:.0f}s "
        f"(last attempt: {last_error}). Start it with `docker compose up -d --build`."
    )


@pytest.fixture
def anonymous(base_url: str) -> Iterator[httpx.Client]:
    """A client with no credentials at all."""

    with httpx.Client(base_url=base_url, timeout=15) as client:
        yield client


@pytest.fixture(scope="session")
def access_token(base_url: str) -> str:
    response = httpx.post(f"{base_url}/v1/auth/login", json=INTERVIEWER, timeout=15)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def owner(base_url: str, access_token: str) -> Iterator[httpx.Client]:
    """The seeded interviewer, who owns every session these tests create."""

    with httpx.Client(
        base_url=base_url,
        timeout=15,
        headers={"Authorization": f"Bearer {access_token}"},
    ) as client:
        yield client


@pytest.fixture
def interview(owner: httpx.Client) -> dict[str, Any]:
    """A fresh draft session owned by the interviewer."""

    response = owner.post(
        "/v1/sessions",
        json={
            "title": unique("Integration interview"),
            "prompt": "Design a URL shortener that serves 10k requests per second.",
            "duration_minutes": 45,
            "scheduled_at": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def guest_token(owner: httpx.Client, interview: dict[str, Any]) -> str:
    """A candidate invitation token for `interview`."""

    response = owner.post(
        f"/v1/sessions/{interview['id']}/guest-links",
        json={"role_granted": "candidate"},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


@pytest.fixture
def guest(
    base_url: str, guest_token: str
) -> Iterator[tuple[httpx.Client, dict[str, Any]]]:
    """A joined candidate: a cookie-carrying client and its participant."""

    with httpx.Client(base_url=base_url, timeout=15) as client:
        response = client.post(
            f"/v1/join/{guest_token}", json={"display_name": unique("Casey")}
        )
        assert response.status_code == 200, response.text
        assert client.cookies.get(GUEST_COOKIE_NAME), "join did not set the guest cookie"
        yield client, response.json()["participant"]
