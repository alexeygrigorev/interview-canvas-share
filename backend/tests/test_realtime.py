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
