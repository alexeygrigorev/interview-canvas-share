from fastapi.testclient import TestClient

from backend.app.store import SEED_GUEST_TOKEN

from .conftest import login


def test_guest_can_inspect_join_read_and_save_canvas(client: TestClient) -> None:
    inspection = client.get(f"/v1/join/{SEED_GUEST_TOKEN}")
    assert inspection.status_code == 200
    assert inspection.json()["link"]["token"] == SEED_GUEST_TOKEN

    joined = client.post(
        f"/v1/join/{SEED_GUEST_TOKEN}",
        json={"display_name": "  Test Guest  "},
    )
    assert joined.status_code == 200
    participant = joined.json()["participant"]
    assert participant["display_name"] == "Test Guest"
    assert "sdip_guest_session=" in joined.headers["set-cookie"]

    detail = client.get("/v1/sessions/ses_url_shortener")
    assert detail.status_code == 200
    assert any(item["id"] == participant["id"] for item in detail.json()["participants"])

    node = {
        "id": "elm_guest_note",
        "kind": "note",
        "created_by": participant["id"],
        "created_at": "2026-08-03T14:00:00Z",
        "updated_at": "2026-08-03T14:00:00Z",
        "componentType": "note",
        "x": 100,
        "y": 100,
        "width": 120,
        "height": 80,
        "label": "Candidate note",
    }
    saved = client.put(
        "/v1/sessions/ses_url_shortener/canvas",
        json={"elements": [node], "actor": participant["id"]},
    )
    assert saved.status_code == 200
    assert saved.json().endswith("Z")
    saved_node = client.get("/v1/sessions/ses_url_shortener/canvas").json()["elements"][0]
    assert saved_node["id"] == node["id"]
    assert saved_node["label"] == node["label"]
    assert saved_node["created_by"] == participant["id"]

    left = client.delete(f"/v1/sessions/ses_url_shortener/participants/{participant['id']}")
    assert left.status_code == 200
    assert left.json() is True
    assert client.get("/v1/sessions/ses_url_shortener").status_code == 401


def test_guest_cannot_save_when_candidate_editing_is_locked(client: TestClient) -> None:
    owner_token = login(client)
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    assert client.patch(
        "/v1/sessions/ses_url_shortener",
        headers=owner_headers,
        json={"candidate_editing_enabled": False},
    ).status_code == 200

    joined = client.post(f"/v1/join/{SEED_GUEST_TOKEN}", json={"display_name": "Locked Candidate"})
    assert joined.status_code == 200
    participant_id = joined.json()["participant"]["id"]
    response = client.put(
        "/v1/sessions/ses_url_shortener/canvas",
        json={"elements": [], "actor": participant_id},
    )

    assert response.status_code == 403


def test_guest_link_is_hashed_and_revocation_returns_gone(client: TestClient, store) -> None:
    token = login(client)
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/v1/sessions/ses_url_shortener/guest-links",
        headers=headers,
        json={"role_granted": "observer"},
    )
    assert created.status_code == 201
    raw_token = created.json()["token"]
    link_id = created.json()["id"]
    token_hash = store.get_guest_link_hash(link_id)
    assert token_hash is not None
    assert raw_token not in token_hash

    assert client.delete(
        f"/v1/sessions/ses_url_shortener/guest-links/{link_id}",
        headers=headers,
    ).json() is True
    revoked = client.get(f"/v1/join/{raw_token}")
    assert revoked.status_code == 410
    assert revoked.json()["code"] == "revoked"


def test_invalid_guest_token_is_not_found(client: TestClient) -> None:
    response = client.get("/v1/join/not-a-real-token")

    assert response.status_code == 404
    assert response.json()["code"] == "invalid_token"
