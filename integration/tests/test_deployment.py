"""The stack answers as a deployment: health, the built SPA, and the API."""

from __future__ import annotations

import re

import httpx


def test_health_endpoint_reports_ok(anonymous: httpx.Client) -> None:
    response = anonymous.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_serves_the_built_frontend(anonymous: httpx.Client) -> None:
    response = anonymous.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<div id=" in response.text or "<script" in response.text


def test_frontend_assets_are_bundled_into_the_image(anonymous: httpx.Client) -> None:
    """The image is only useful if the assets the shell references exist."""

    index = anonymous.get("/").text
    assets = re.findall(r'(?:src|href)="(/(?:assets|_build)/[^"]+)"', index)
    assert assets, f"no bundled assets referenced from the SPA shell: {index[:500]}"

    for asset in assets[:5]:
        response = anonymous.get(asset)
        assert response.status_code == 200, f"{asset} -> {response.status_code}"


def test_unknown_frontend_route_falls_back_to_the_shell(anonymous: httpx.Client) -> None:
    response = anonymous.get("/room/does-not-exist")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")


def test_unknown_api_route_stays_json(anonymous: httpx.Client) -> None:
    """An API typo must not fall through to the SPA shell."""

    response = anonymous.get("/v1/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["code"] == "not_found"


def test_openapi_document_is_served(anonymous: httpx.Client) -> None:
    response = anonymous.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert "/v1/sessions" in schema["paths"]
    assert "x-websocket" in schema
