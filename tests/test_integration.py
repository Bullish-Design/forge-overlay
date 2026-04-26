from __future__ import annotations

import json

import httpx
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

from forge_overlay.app import create_app
from forge_overlay.config import Config


class TestAppIntegration:
    """Integration tests for core app routes and behavior."""

    def test_rebuild_webhook_returns_204(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.post("/internal/rebuild", json={"type": "rebuilt"})
        assert resp.status_code == 204

    def test_rebuild_with_empty_body_returns_204(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.post("/internal/rebuild")
        assert resp.status_code == 204

    def test_rebuild_with_garbage_body_returns_204(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.post("/internal/rebuild", content=b"garbage")
        assert resp.status_code == 204

    def test_rebuild_triggers_sse_event(self, demo_config: Config, monkeypatch) -> None:
        class FakeBroker:
            def __init__(self) -> None:
                self.events: list[str] = []

            def publish(self, event: str) -> None:
                self.events.append(event)

            async def subscribe(self):
                for event in self.events:
                    yield event

        monkeypatch.setattr("forge_overlay.app.EventBroker", FakeBroker)
        app = create_app(demo_config)
        client = TestClient(app)

        resp = client.post("/internal/rebuild")
        assert resp.status_code == 204

        with client.stream("GET", "/ops/events") as response:
            assert response.status_code == 200
            data_lines = [line for line in response.iter_lines() if line and line.startswith("data:")]

        assert data_lines
        assert json.loads(data_lines[0].removeprefix("data:").strip()) == {"type": "rebuilt"}

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

    def test_trailing_slash_redirect_preserves_query(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app, follow_redirects=False)
        resp = client.get("/about/?x=1&y=2")
        assert resp.status_code == 301
        assert resp.headers["location"] == "/about?x=1&y=2"

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

    def test_overlay_traversal_returns_403(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/ops/%2e%2e/%2e%2e/etc/passwd")
        assert resp.status_code == 403

    def test_overlay_missing_file_returns_404(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/ops/missing.js")
        assert resp.status_code == 404

    def test_css_not_injected(self, config: Config) -> None:
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/style.css")
        assert resp.status_code == 200
        assert "ops.js" not in resp.text

    def test_api_proxy_route(self, config: Config, monkeypatch) -> None:
        async def fake_proxy(
            _request,
            upstream: str,
            _client: httpx.AsyncClient,
        ) -> JSONResponse:
            assert upstream == config.api_upstream
            return JSONResponse({"proxied": True}, status_code=200)

        monkeypatch.setattr("forge_overlay.app.proxy_request", fake_proxy)
        app = create_app(config)
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"proxied": True}

    def test_demo_root_serves_vault_home(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Welcome to the Demo Vault" in resp.text

    def test_demo_nested_clean_url_notes(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/notes/day-1")
        assert resp.status_code == 200
        assert "Day 1 Notes" in resp.text

    def test_demo_nested_clean_url_projects(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/projects/forge")
        assert resp.status_code == 200
        assert "Forge Project" in resp.text

    def test_demo_404_serves_custom_page(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/nope")
        assert resp.status_code == 404
        assert "Page not found" in resp.text

    def test_demo_css_asset_not_injected(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/style.css")
        assert resp.status_code == 200
        assert "ops.js" not in resp.text

    def test_demo_binary_asset_served(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/logo.png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    def test_demo_html_pages_are_injected(self, demo_config: Config) -> None:
        app = create_app(demo_config)
        client = TestClient(app)
        resp = client.get("/notes/day-1")
        assert resp.status_code == 200
        assert "ops.js" in resp.text
        assert "ops.css" in resp.text

    def test_lifespan_closes_http_client(self, config: Config, monkeypatch) -> None:
        closed_calls: list[int] = []
        original_aclose = httpx.AsyncClient.aclose

        async def tracked_aclose(self: httpx.AsyncClient) -> None:
            closed_calls.append(id(self))
            await original_aclose(self)

        monkeypatch.setattr(httpx.AsyncClient, "aclose", tracked_aclose)

        app = create_app(config)
        with TestClient(app):
            pass

        assert len(closed_calls) == 1
