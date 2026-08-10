"""An interview's whole lifecycle, through the deployed API and PostgreSQL."""

from __future__ import annotations

from typing import Any

import httpx


def test_created_session_is_readable_and_listed(
    owner: httpx.Client, interview: dict[str, Any]
) -> None:
    assert interview["state"] == "draft"

    detail = owner.get(f"/v1/sessions/{interview['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["session"]["title"] == interview["title"]

    listed = owner.get("/v1/sessions")
    assert listed.status_code == 200, listed.text
    assert interview["id"] in {item["id"] for item in listed.json()}


def test_session_transitions_draft_to_archived(
    owner: httpx.Client, interview: dict[str, Any]
) -> None:
    session_id = interview["id"]

    started = owner.post(f"/v1/sessions/{session_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["state"] == "live"
    assert started.json()["started_at"] is not None

    # Only a draft can start, and the API says so rather than silently redoing it.
    again = owner.post(f"/v1/sessions/{session_id}/start")
    assert again.status_code == 409
    assert again.json()["code"] == "invalid_session_state"

    ended = owner.post(f"/v1/sessions/{session_id}/end")
    assert ended.status_code == 200, ended.text
    assert ended.json()["state"] == "ended"

    archived = owner.post(f"/v1/sessions/{session_id}/archive")
    assert archived.status_code == 200, archived.text
    assert archived.json()["state"] == "archived"


def test_settings_survive_a_round_trip_through_the_database(
    owner: httpx.Client, interview: dict[str, Any]
) -> None:
    patched = owner.patch(
        f"/v1/sessions/{interview['id']}",
        json={"candidate_editing_enabled": False, "title": "Renamed by integration"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["candidate_editing_enabled"] is False

    reread = owner.get(f"/v1/sessions/{interview['id']}")
    assert reread.json()["session"]["title"] == "Renamed by integration"
    assert reread.json()["session"]["candidate_editing_enabled"] is False


def test_unknown_session_is_a_json_404(owner: httpx.Client) -> None:
    response = owner.get("/v1/sessions/ses_does_not_exist")
    assert response.status_code == 404
    assert response.json()["code"] == "session_not_found"


def test_sessions_require_authentication(anonymous: httpx.Client) -> None:
    assert anonymous.get("/v1/sessions").status_code == 401
