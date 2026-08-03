from fastapi.testclient import TestClient

from .conftest import login


def test_seeded_sessions_are_visible_and_ordered(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/v1/sessions", headers=auth_headers)

    assert response.status_code == 200
    sessions = response.json()
    assert [session["id"] for session in sessions] == [
        "ses_url_shortener",
        "ses_ride_matching",
        "ses_metrics_pipeline",
    ]
    assert sessions[0]["state"] == "live"
    assert len(sessions[0]["participants"]) == 3
    assert sessions[0]["link"]["token"] == "[redacted]"


def test_session_detail_only_returns_active_participants(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.get("/v1/sessions/ses_ride_matching", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["participants"] == []


def test_create_and_transition_session(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post(
        "/v1/sessions",
        headers=auth_headers,
        json={
            "title": "Design an event bus",
            "prompt": "Design a multi-tenant event bus.",
            "duration_minutes": 45,
            "scheduled_at": None,
        },
    )
    assert created.status_code == 201
    session_id = created.json()["id"]
    assert created.json()["state"] == "draft"

    canvas = client.get(f"/v1/sessions/{session_id}/canvas", headers=auth_headers)
    assert canvas.status_code == 200
    assert canvas.json()["elements"] == []

    started = client.post(f"/v1/sessions/{session_id}/start", headers=auth_headers)
    assert started.status_code == 200
    assert started.json()["state"] == "live"
    assert client.post(f"/v1/sessions/{session_id}/start", headers=auth_headers).status_code == 409

    updated = client.patch(
        f"/v1/sessions/{session_id}",
        headers=auth_headers,
        json={"candidate_editing_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["candidate_editing_enabled"] is False

    ended = client.post(f"/v1/sessions/{session_id}/end", headers=auth_headers)
    assert ended.status_code == 200
    assert ended.json()["state"] == "ended"
    archived = client.post(f"/v1/sessions/{session_id}/archive", headers=auth_headers)
    assert archived.status_code == 200
    assert archived.json()["state"] == "archived"


def test_non_owner_cannot_change_another_users_session(client: TestClient) -> None:
    jordan_token = login(client, "jordan@northwind.dev")
    headers = {"Authorization": f"Bearer {jordan_token}"}

    response = client.patch(
        "/v1/sessions/ses_url_shortener",
        headers=headers,
        json={"title": "Not Jordan's session"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


def test_empty_session_patch_is_contract_validation_error(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.patch("/v1/sessions/ses_url_shortener", headers=auth_headers, json={})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
