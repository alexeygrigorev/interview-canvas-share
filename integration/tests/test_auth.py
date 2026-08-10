"""Login against the seeded demo data and use the token it returns."""

from __future__ import annotations

import httpx

from helpers import INTERVIEWER


def test_login_returns_a_token_and_the_user(anonymous: httpx.Client) -> None:
    response = anonymous.post("/v1/auth/login", json=INTERVIEWER)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == INTERVIEWER["email"]


def test_login_rejects_a_wrong_password(anonymous: httpx.Client) -> None:
    response = anonymous.post(
        "/v1/auth/login", json={**INTERVIEWER, "password": "not-the-password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "invalid_credentials"


def test_current_user_requires_a_token(anonymous: httpx.Client) -> None:
    assert anonymous.get("/v1/me").status_code == 401


def test_current_user_is_the_token_holder(owner: httpx.Client) -> None:
    response = owner.get("/v1/me")
    assert response.status_code == 200, response.text
    assert response.json()["email"] == INTERVIEWER["email"]
