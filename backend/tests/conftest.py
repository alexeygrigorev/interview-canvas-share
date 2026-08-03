from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.store import InMemoryStore


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore.seeded()


@pytest.fixture
def client(store: InMemoryStore) -> Iterator[TestClient]:
    with TestClient(create_app(store)) as test_client:
        yield test_client


def login(client: TestClient, email: str = "avery@northwind.dev") -> str:
    response = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "demo-password"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {login(client)}"}
