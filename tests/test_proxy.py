from __future__ import annotations

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient

from forge_overlay.proxy import proxy_request


def _build_app(upstream_client: httpx.AsyncClient, methods: list[str] | None = None) -> Starlette:
    async def proxy_route(request: Request):
        return await proxy_request(request, "http://upstream:3000", upstream_client)

    route_methods = methods or ["GET"]
    return Starlette(routes=[Route("/api/{path:path}", proxy_route, methods=route_methods)])


class TestProxy:
    """Proxy tests using httpx mock transport to simulate upstream."""

    async def test_forwards_get(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url).startswith("http://upstream:3000/api/vault/notes")
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/vault/notes")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        await client.aclose()

    async def test_forwards_post_body(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                201,
                content=request.content,
                headers={"content-type": "application/json"},
            )

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client, methods=["POST"])

        test_client = TestClient(app)
        resp = test_client.post("/api/vault/notes", json={"title": "test"})
        assert resp.status_code == 201

        await client.aclose()

    async def test_forwards_query_string(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "q=hello" in str(request.url)
            return httpx.Response(200, json={"results": []})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/search?q=hello")
        assert resp.status_code == 200

        await client.aclose()

    async def test_strips_hop_by_hop_request_headers(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["connection"] != "close"
            assert "keep-alive" not in request.headers
            assert request.headers["x-custom"] == "yes"
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get(
            "/api/headers",
            headers={"Connection": "close", "Keep-Alive": "timeout=5", "X-Custom": "yes"},
        )
        assert resp.status_code == 200

        await client.aclose()

    async def test_does_not_forward_client_host_header(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["host"] == "upstream:3000"
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/host-check", headers={"Host": "evil.example"})
        assert resp.status_code == 200

        await client.aclose()

    async def test_strips_hop_by_hop_response_headers(self) -> None:
        async def mock_handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                text="ok",
                headers={
                    "Transfer-Encoding": "chunked",
                    "Connection": "keep-alive",
                    "X-Upstream": "present",
                },
            )

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/header-roundtrip")
        assert resp.status_code == 200
        assert "connection" not in resp.headers
        assert "transfer-encoding" not in resp.headers
        assert resp.headers["x-upstream"] == "present"

        await client.aclose()

    async def test_upstream_connect_error_returns_502(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("cannot connect", request=request)

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/unavailable")
        assert resp.status_code == 502
        assert resp.json() == {"error": "upstream_unavailable"}

        await client.aclose()

    async def test_upstream_timeout_returns_502(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://upstream:3000")
        app = _build_app(client)

        test_client = TestClient(app)
        resp = test_client.get("/api/slow")
        assert resp.status_code == 502
        assert resp.json() == {"error": "upstream_unavailable"}

        await client.aclose()
