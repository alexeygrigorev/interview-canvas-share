import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Importing the ASGI module constructs its production-style module-level app.
# Keep that app isolated from the filesystem; individual tests use temporary files.
os.environ.setdefault("SDIP_DATABASE_URL", "sqlite://")

from backend.app.main import create_app
from backend.app.store import DatabaseStore


@pytest.fixture
def store(tmp_path) -> DatabaseStore:
    return DatabaseStore.seeded(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(store: DatabaseStore) -> Iterator[TestClient]:
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
