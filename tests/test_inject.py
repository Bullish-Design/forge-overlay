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
