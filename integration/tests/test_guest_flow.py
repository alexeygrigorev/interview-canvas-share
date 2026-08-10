"""The candidate's path: an invitation link, a cookie, and a shared canvas."""

from __future__ import annotations

from typing import Any

import httpx
from helpers import node_element, unique


def test_token_is_inspectable_without_credentials(
    anonymous: httpx.Client, interview: dict[str, Any], guest_token: str
) -> None:
    """The join page renders before anyone has identified themselves."""

    response = anonymous.get(f"/v1/join/{guest_token}")
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["session"]["id"] == interview["id"]
    assert body["link"]["role_granted"] == "candidate"
    assert body["activeCount"] == 0


def test_unknown_token_is_rejected(anonymous: httpx.Client) -> None:
    response = anonymous.get("/v1/join/not-a-real-token")
    assert response.status_code == 404
    assert response.json()["code"] == "invalid_token"


def test_joining_makes_the_guest_a_participant(
    owner: httpx.Client,
    interview: dict[str, Any],
    guest: tuple[httpx.Client, dict[str, Any]],
) -> None:
    _, participant = guest
    assert participant["role"] == "candidate"

    detail = owner.get(f"/v1/sessions/{interview['id']}")
    participants = {p["id"]: p for p in detail.json()["participants"]}
    assert participant["id"] in participants
    assert participants[participant["id"]]["display_name"] == participant["display_name"]


def test_guest_cookie_grants_access_to_the_session(
    interview: dict[str, Any], guest: tuple[httpx.Client, dict[str, Any]]
) -> None:
    client, _ = guest

    detail = client.get(f"/v1/sessions/{interview['id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["session"]["id"] == interview["id"]

    canvas = client.get(f"/v1/sessions/{interview['id']}/canvas")
    assert canvas.status_code == 200, canvas.text
    assert canvas.json()["session_id"] == interview["id"]


def test_guest_without_the_cookie_is_refused(
    anonymous: httpx.Client, interview: dict[str, Any]
) -> None:
    response = anonymous.get(f"/v1/sessions/{interview['id']}/canvas")
    assert response.status_code == 401


def test_candidate_edit_is_persisted_and_visible_to_the_owner(
    owner: httpx.Client,
    interview: dict[str, Any],
    guest: tuple[httpx.Client, dict[str, Any]],
) -> None:
    client, participant = guest
    label = unique("Candidate node")
    element = node_element(participant["id"], label)

    saved = client.put(
        f"/v1/sessions/{interview['id']}/canvas",
        json={"elements": [element], "actor": participant["id"]},
    )
    assert saved.status_code == 200, saved.text

    # Read back through a different client and credential: the element went to
    # the database, not just into the writer's own process.
    canvas = owner.get(f"/v1/sessions/{interview['id']}/canvas")
    assert canvas.status_code == 200, canvas.text
    assert [e["label"] for e in canvas.json()["elements"]] == [label]


def test_revoked_link_stops_working(
    owner: httpx.Client,
    anonymous: httpx.Client,
    interview: dict[str, Any],
) -> None:
    created = owner.post(f"/v1/sessions/{interview['id']}/guest-links")
    assert created.status_code == 201, created.text
    link = created.json()

    revoked = owner.delete(f"/v1/sessions/{interview['id']}/guest-links/{link['id']}")
    assert revoked.status_code == 200, revoked.text

    response = anonymous.get(f"/v1/join/{link['token']}")
    assert response.status_code == 410
    assert response.json()["code"] == "revoked"
