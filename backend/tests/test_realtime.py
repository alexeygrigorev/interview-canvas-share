from fastapi.testclient import TestClient

from .conftest import login


def test_realtime_document_message_is_broadcast_and_persisted(client: TestClient) -> None:
    token = login(client)
    message = {
        "type": "document_update",
        "sessionId": "ses_url_shortener",
        "elements": [],
        "actor": "par_avery_url",
    }

    with client.websocket_connect(
        "/v1/sessions/ses_url_shortener/realtime",
        headers={"Authorization": f"Bearer {token}"},
    ) as websocket:
        websocket.send_json(message)
        assert websocket.receive_json() == message

    canvas = client.get(
        "/v1/sessions/ses_url_shortener/canvas",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert canvas.status_code == 200
    assert canvas.json()["elements"] == []


def test_realtime_accepts_browser_bearer_subprotocol(client: TestClient) -> None:
    token = login(client)
    with client.websocket_connect(
        "/v1/sessions/ses_url_shortener/realtime",
        subprotocols=["sdip", f"bearer.{token}"],
    ) as websocket:
        assert websocket.accepted_subprotocol == "sdip"


def test_realtime_rejects_server_generated_client_messages(client: TestClient) -> None:
    token = login(client)
    with client.websocket_connect(
        "/v1/sessions/ses_url_shortener/realtime",
        headers={"Authorization": f"Bearer {token}"},
    ) as websocket:
        websocket.send_json(
            {
                "type": "session_ended",
                "sessionId": "ses_url_shortener",
            }
        )
        assert websocket.receive_json()["code"] == "validation_error"


def test_session_updates_are_published_to_room_clients(client: TestClient) -> None:
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    with client.websocket_connect(
        "/v1/sessions/ses_url_shortener/realtime",
        headers=headers,
    ) as websocket:
        response = client.patch(
            "/v1/sessions/ses_url_shortener",
            headers=headers,
            json={"cursors_visible": False},
        )
        assert response.status_code == 200
        event = websocket.receive_json()
        assert event["type"] == "permission_changed"
        assert event["sessionId"] == "ses_url_shortener"
        assert event["session"]["cursors_visible"] is False
