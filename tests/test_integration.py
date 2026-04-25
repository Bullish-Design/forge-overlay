from __future__ import annotations

from starlette.testclient import TestClient

from forge_overlay.app import create_app
from forge_overlay.config import Config


class TestRebuildToSSE:
    """Integration tests for core app routes and behavior."""

    def test_rebuild_webhook_returns_204(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.post("/internal/rebuild", json={"type": "rebuilt"})
        assert resp.status_code == 204

    def test_site_root_serves_index(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Home" in resp.text
        assert "ops.js" in resp.text

    def test_clean_url(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/about")
        assert resp.status_code == 200
        assert "About" in resp.text

    def test_trailing_slash_redirect(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/about/")
        assert resp.status_code == 301
        assert resp.headers["location"] == "/about"

    def test_404_custom_page(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/nonexistent")
        assert resp.status_code == 404
        assert "Not Found" in resp.text
        assert "ops.js" in resp.text

    def test_overlay_static_serves_js(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/ops/ops.js")
        assert resp.status_code == 200
        assert "overlay JS" in resp.text

    def test_css_not_injected(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/style.css")
        assert resp.status_code == 200
        assert "ops.js" not in resp.text
