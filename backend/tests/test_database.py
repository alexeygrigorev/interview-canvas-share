from backend.app.database import DATABASE_URL_ENV, database_url
from backend.app.store import DatabaseStore


def test_database_url_comes_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(DATABASE_URL_ENV, "sqlite:////tmp/custom-sdip.db")

    assert database_url() == "sqlite:////tmp/custom-sdip.db"


def test_data_persists_across_repository_instances(tmp_path) -> None:
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    first = DatabaseStore.seeded(url)
    created = first.create_session(
        owner_user_id="usr_avery",
        title="Persistent interview",
        prompt="Prove that this record survives a new repository instance.",
        duration_minutes=30,
        scheduled_at=None,
    )

    second = DatabaseStore.from_url(url)

    assert second.get_session(created.id) == created
