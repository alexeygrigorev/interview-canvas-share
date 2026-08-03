from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.store import DatabaseStore


def test_serves_static_files_and_spa_fallback(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text("<h1>frontend</h1>")
    (assets_dir / "app.js").write_text("console.log('frontend')")

    app = create_app(DatabaseStore.seeded("sqlite://"), static_dir=static_dir)
    with TestClient(app) as client:
        assert client.get("/").text == "<h1>frontend</h1>"
        assert client.get("/room/example").text == "<h1>frontend</h1>"
        assert client.get("/assets/app.js").text == "console.log('frontend')"

        api_response = client.get("/v1/does-not-exist")
        assert api_response.status_code == 404
        assert api_response.json()["code"] == "not_found"
