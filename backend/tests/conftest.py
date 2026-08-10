import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

# Importing the ASGI module constructs its production-style module-level app.
# Keep that app isolated from the filesystem; individual tests use temporary files.
os.environ.setdefault("SDIP_DATABASE_URL", "sqlite://")

from backend.app.database import Base, create_database_engine
from backend.app.main import create_app
from backend.app.store import DatabaseStore

# Point this at a PostgreSQL URL to run the whole suite against PostgreSQL, e.g.
# SDIP_TEST_DATABASE_URL=postgresql://sdip:sdip@localhost:5432/sdip make test
TEST_DATABASE_URL_ENV = "SDIP_TEST_DATABASE_URL"


@pytest.fixture
def database_url(tmp_path) -> Iterator[str]:
    url = os.getenv(TEST_DATABASE_URL_ENV) or f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_database_engine(url)
    # A shared server keeps rows between tests the way a temporary file does not.
    Base.metadata.drop_all(engine)
    try:
        yield url
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def store(database_url: str) -> DatabaseStore:
    return DatabaseStore.seeded(database_url)


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
