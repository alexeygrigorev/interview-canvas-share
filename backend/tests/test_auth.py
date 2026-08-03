from fastapi.testclient import TestClient

from backend.app.store import UserRecord

from .conftest import login


def test_protected_endpoints_require_a_bearer_token(client: TestClient) -> None:
    response = client.get("/v1/me")

    assert response.status_code == 401
    assert response.json() == {
        "code": "authentication_required",
        "message": "Authentication is required.",
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_verifies_hashed_password_and_returns_bearer_token(
    client: TestClient,
    store,
) -> None:
    user_record = store.users["usr_avery"]
    assert isinstance(user_record, UserRecord)
    assert user_record.password_hash.startswith("$argon2")
    assert "demo-password" not in user_record.password_hash

    bad = client.post(
        "/v1/auth/login",
        json={"email": "avery@northwind.dev", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_credentials"

    token = login(client)
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "avery@northwind.dev"
    assert "password_hash" not in response.json()


def test_invalid_bearer_token_is_rejected(client: TestClient) -> None:
    response = client.get("/v1/me", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"
