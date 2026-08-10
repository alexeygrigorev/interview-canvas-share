"""The WebSocket gateway: two clients in one room, over the real network.

This is the part the deployment can break on its own - a proxy that drops the
Upgrade header, or a second app replica splitting the room - so it is worth
asserting against the running stack and not only in-process.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from helpers import next_message, node_element, room, unique
from websockets.exceptions import InvalidStatus


def test_document_update_reaches_the_other_client_and_the_database(
    base_url: str,
    access_token: str,
    owner: httpx.Client,
    interview: dict[str, Any],
    guest: tuple[httpx.Client, dict[str, Any]],
) -> None:
    client, participant = guest
    cookie = client.cookies.get("sdip_guest_session")
    label = unique("Realtime node")
    element = node_element(participant["id"], label)

    with room(base_url, interview["id"], token=access_token) as interviewer_socket:
        with room(base_url, interview["id"], cookie=cookie) as candidate_socket:
            candidate_socket.send(
                json.dumps(
                    {
                        "type": "document_update",
                        "sessionId": interview["id"],
                        "elements": [element],
                        "actor": participant["id"],
                    }
                )
            )

            received = next_message(interviewer_socket, "document_update")

    assert [e["label"] for e in received["elements"]] == [label]

    # The gateway persists what it fans out, so a late joiner sees it too.
    canvas = owner.get(f"/v1/sessions/{interview['id']}/canvas")
    assert [e["label"] for e in canvas.json()["elements"]] == [label]


def test_rest_canvas_save_is_broadcast_to_the_room(
    base_url: str,
    access_token: str,
    owner: httpx.Client,
    interview: dict[str, Any],
    guest: tuple[httpx.Client, dict[str, Any]],
) -> None:
    """A candidate watching the room sees an owner's plain HTTP save."""

    client, _ = guest
    cookie = client.cookies.get("sdip_guest_session")
    label = unique("Interviewer node")

    with room(base_url, interview["id"], cookie=cookie) as candidate_socket:
        saved = owner.put(
            f"/v1/sessions/{interview['id']}/canvas",
            json={
                "elements": [node_element(interview["owner_user_id"], label)],
                "actor": interview["owner_user_id"],
            },
        )
        assert saved.status_code == 200, saved.text

        received = next_message(candidate_socket, "document_update")

    assert [e["label"] for e in received["elements"]] == [label]


def test_ending_the_session_is_announced_to_the_room(
    base_url: str,
    access_token: str,
    owner: httpx.Client,
    interview: dict[str, Any],
) -> None:
    with room(base_url, interview["id"], token=access_token) as socket:
        assert owner.post(f"/v1/sessions/{interview['id']}/start").status_code == 200
        assert next_message(socket, "permission_changed")["session"]["state"] == "live"

        assert owner.post(f"/v1/sessions/{interview['id']}/end").status_code == 200
        assert next_message(socket, "session_ended")["sessionId"] == interview["id"]


def test_room_refuses_an_unauthenticated_client(
    base_url: str, interview: dict[str, Any]
) -> None:
    """No token and no guest cookie: the handshake never completes."""

    with pytest.raises((InvalidStatus, OSError)):
        with room(base_url, interview["id"]) as socket:
            socket.recv(timeout=10)
