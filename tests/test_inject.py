from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from forge_overlay.inject import InjectMiddleware


def _make_app(html_body: str = "<html><head></head><body>hi</body></html>") -> InjectMiddleware:
    async def homepage(_request: object) -> HTMLResponse:
        return HTMLResponse(html_body)

    async def plain(_request: object) -> PlainTextResponse:
        return PlainTextResponse("not html")

    app = Starlette(
        routes=[
            Route("/", homepage),
            Route("/plain", plain),
        ]
    )
    return InjectMiddleware(app)


class TestInjectMiddleware:
    async def test_non_http_scope_passthrough(self) -> None:
        inner_called = False

        async def mock_app(scope, receive, send) -> None:
            nonlocal inner_called
            inner_called = True
            assert scope["type"] == "lifespan"
            await send({"type": "lifespan.startup.complete"})

        middleware = InjectMiddleware(mock_app)

        async def dummy_receive():
            return {"type": "lifespan.startup"}

        async def dummy_send(_message):
            return None

        await middleware({"type": "lifespan"}, dummy_receive, dummy_send)
        assert inner_called

    def test_injects_into_html(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/")
        assert resp.status_code == 200
        assert "ops/ops.js" in resp.text
        assert "ops/ops.css" in resp.text
        # Snippet appears before </head>
        assert resp.text.index("ops.js") < resp.text.index("</head>")

    def test_skips_non_html(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/plain")
        assert "ops.js" not in resp.text

    def test_skips_html_without_head(self) -> None:
        app = _make_app("<html><body>no head tag</body></html>")
        client = TestClient(app)
        resp = client.get("/")
        # No </head> means no injection
        assert "ops.js" not in resp.text

    def test_content_length_updated(self) -> None:
        client = TestClient(_make_app())
        resp = client.get("/")
        assert int(resp.headers["content-length"]) == len(resp.content)

    def test_injects_with_charset_content_type(self) -> None:
        async def homepage(_request: object):
            return HTMLResponse(
                "<html><head></head><body>charset</body></html>",
                headers={"content-type": "text/html; charset=utf-8"},
            )

        app = Starlette(routes=[Route("/", homepage)])
        client = TestClient(InjectMiddleware(app))
        resp = client.get("/")
        assert "ops.js" in resp.text

    def test_injects_with_uppercase_head_tag(self) -> None:
        app = _make_app("<html><HEAD></HEAD><body>hi</body></html>")
        client = TestClient(app)
        resp = client.get("/")
        assert "ops.js" in resp.text

    def test_injects_when_body_is_chunked(self) -> None:
        async def chunked_app(scope, _receive, send):
            assert scope["type"] == "http"
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/html; charset=utf-8")],
                }
            )
            await send({"type": "http.response.body", "body": b"<html><head>", "more_body": True})
            await send({"type": "http.response.body", "body": b"</head><body>ok</body></html>"})

        client = TestClient(InjectMiddleware(chunked_app))
        resp = client.get("/")
        assert resp.status_code == 200
        assert "ops.js" in resp.text
