from __future__ import annotations

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Route
from starlette.testclient import TestClient

from forge_overlay.proxy import proxy_request


class TestProxy:
    """Proxy tests using httpx mock transport to simulate upstream."""

    async def test_forwards_get(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url).startswith("http://upstream:3000/api/vault/notes")
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[Route("/api/{path:path}", proxy_route)])

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
        client = httpx.AsyncClient(transport=transport)

        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[Route("/api/{path:path}", proxy_route, methods=["POST"])])

        test_client = TestClient(app)
        resp = test_client.post("/api/vault/notes", json={"title": "test"})
        assert resp.status_code == 201

        await client.aclose()

    async def test_forwards_query_string(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "q=hello" in str(request.url)
            return httpx.Response(200, json={"results": []})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[Route("/api/{path:path}", proxy_route)])

        test_client = TestClient(app)
        resp = test_client.get("/api/search?q=hello")
        assert resp.status_code == 200

        await client.aclose()
