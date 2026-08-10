import pytest

from backend.app.database import (
    DATABASE_URL_ENV,
    CanvasRow,
    ParticipantRow,
    create_database_engine,
    database_url,
    normalize_database_url,
)
from backend.app.store import DatabaseStore


def test_database_url_comes_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:////tmp/custom-sdip.db")

    assert database_url() == "sqlite:////tmp/custom-sdip.db"


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "postgresql://sdip:sdip@localhost:5432/sdip",
            "postgresql+psycopg://sdip:sdip@localhost:5432/sdip",
        ),
        ("postgres://sdip:sdip@db/sdip", "postgresql+psycopg://sdip:sdip@db/sdip"),
        ("postgresql+psycopg://sdip@db/sdip", "postgresql+psycopg://sdip@db/sdip"),
        ("sqlite:///./sdip.db", "sqlite:///./sdip.db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_postgres_urls_resolve_to_the_installed_driver(url: str, expected: str) -> None:
    assert normalize_database_url(url) == expected


def test_postgres_engine_uses_a_configurable_pool(monkeypatch) -> None:
    monkeypatch.setenv("SDIP_DB_POOL_SIZE", "7")

    engine = create_database_engine("postgres://sdip:sdip@localhost:5432/sdip")

    assert engine.dialect.driver == "psycopg"
    assert engine.pool.size() == 7


def test_json_columns_use_jsonb_on_postgres() -> None:
    postgres = create_database_engine("postgres://sdip:sdip@localhost:5432/sdip")
    sqlite = create_database_engine("sqlite://")

    for column in (CanvasRow.__table__.c.elements, ParticipantRow.__table__.c.cursor):
        assert "JSONB" in str(column.type.compile(postgres.dialect))
        assert "JSON" == str(column.type.compile(sqlite.dialect))


def test_data_persists_across_repository_instances(database_url: str) -> None:
    first = DatabaseStore.seeded(database_url)
    created = first.create_session(
        owner_user_id="usr_avery",
        title="Persistent interview",
        prompt="Prove that this record survives a new repository instance.",
        duration_minutes=30,
        scheduled_at=None,
    )

    second = DatabaseStore.from_url(database_url)

    assert second.get_session(created.id) == created
