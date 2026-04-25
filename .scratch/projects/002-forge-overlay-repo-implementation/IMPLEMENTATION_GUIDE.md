# Implementation Guide: forge-overlay

Updated: 2026-04-25

This guide provides step-by-step instructions for implementing the `forge-overlay` service from the current template repo state. Each section contains the exact file contents, rationale, and test expectations needed to execute without ambiguity.

---

## Table of Contents

1. [Starting State](#starting-state)
2. [M0 — Bootstrap](#m0--bootstrap)
3. [M1 — Static Serving + HTML Injection](#m1--static-serving--html-injection)
4. [M2 — Events + Proxy](#m2--events--proxy)
5. [M3 — App Wiring + Integration](#m3--app-wiring--integration)
6. [M4 — Readiness](#m4--readiness)
7. [Reference: Route Table](#reference-route-table)
8. [Reference: kiln-fork Integration](#reference-kiln-fork-integration)

---

## Starting State

The repo is a Python template with:
- `pyproject.toml` — hatchling build, Python >=3.13, only `pydantic` as a dep
- `devenv.nix` / `devenv.yaml` — nix-based dev environment with Python 3.13 + uv
- No `src/` directory, no `tests/` directory, no application code

---

## M0 — Bootstrap

### 0.1 Update `pyproject.toml`

Replace the dependencies and dev-dependencies sections. Keep everything else unchanged.

**Runtime dependencies** (replace the `dependencies` list):
```toml
dependencies = [
  "starlette>=0.46",
  "sse-starlette>=2.0",
  "httpx>=0.28",
  "uvicorn[standard]>=0.34",
]
```

**Dev dependencies** (replace `[project.optional-dependencies] dev`):
```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.26",
  "pytest-cov>=6.0",
  "httpx>=0.28",
  "anyio>=4.9",
  "mypy>=1.10",
  "ruff>=0.5.0",
]
```

Add the pytest-asyncio mode setting under `[tool.pytest.ini_options]`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-q --cov=forge_overlay --cov-report=term-missing"
testpaths = ["tests"]
```

Add the console script entrypoint:
```toml
[project.scripts]
forge-overlay = "forge_overlay.main:main"
```

**Rationale:**
- `starlette` is the ASGI framework (lightweight, async-native).
- `sse-starlette` provides SSE response helpers.
- `httpx` is the async HTTP client for the `/api/*` proxy and is also used in tests.
- `uvicorn[standard]` is the ASGI server with uvloop/httptools.
- `pytest-asyncio` enables `async def test_*` functions.
- `pydantic` is removed — the overlay service doesn't need schema validation; config uses a simple dataclass.

### 0.2 Create Directory Structure

```
src/
  forge_overlay/
    __init__.py
    config.py
    static_handler.py
    inject.py
    events.py
    proxy.py
    app.py
    main.py
tests/
  __init__.py
  conftest.py
  test_static_handler.py
  test_inject.py
  test_events.py
  test_proxy.py
  test_integration.py
```

### 0.3 Create `src/forge_overlay/__init__.py`

```python
"""forge-overlay: browser-facing HTTP edge service for Forge v2."""
```

### 0.4 Create `tests/__init__.py`

Empty file.

### 0.5 Install and Verify

```bash
uv sync --all-extras
uv run python -c "import forge_overlay; print('OK')"
```

---

## M1 — Static Serving + HTML Injection

### 1.1 `src/forge_overlay/config.py`

Stub the config early so other modules can import it. Full wiring happens in M3.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Runtime configuration for forge-overlay."""

    # Directory containing the built site output (kiln's --output dir)
    site_dir: Path = field(default_factory=lambda: Path("public"))

    # Directory containing overlay static assets (ops.js, ops.css)
    overlay_dir: Path = field(default_factory=lambda: Path("overlay"))

    # Upstream URL for /api/* proxy (obsidian-agent)
    api_upstream: str = "http://127.0.0.1:3000"

    # Host and port for the overlay server itself
    host: str = "127.0.0.1"
    port: int = 8080
```

**Key points:**
- `frozen=True` makes config immutable after creation.
- Plain `dataclass` — no pydantic needed.
- All fields have sensible defaults that can be overridden from CLI args or env vars (wired in M3).

### 1.2 `src/forge_overlay/static_handler.py`

This module resolves a URL path to a file in `site_dir` using kiln-compatible clean URL rules, then returns a Starlette `Response`.

```python
from __future__ import annotations

import mimetypes
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, Response

# Resolution order (matches kiln dev-server behavior):
#   1. Exact file match
#   2. <path>.html
#   3. <path>/index.html
#   4. 404.html fallback (if present)


def resolve_file(site_dir: Path, url_path: str) -> Path | None:
    """Resolve a URL path to a file on disk. Returns None if not found."""
    # Normalize: strip leading slash, reject path traversal
    clean = url_path.strip("/")

    # Candidate paths in priority order
    if clean == "":
        candidates = [site_dir / "index.html"]
    else:
        candidates = [
            site_dir / clean,
            site_dir / f"{clean}.html",
            site_dir / clean / "index.html",
        ]

    for candidate in candidates:
        # Resolve symlinks and verify the file is inside site_dir
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and _is_within(resolved, site_dir.resolve()):
            return resolved

    return None


def build_response(file_path: Path) -> Response:
    """Build a FileResponse with the correct content type."""
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=file_path, media_type=content_type)


def build_404(site_dir: Path) -> Response:
    """Return a 404 response, using custom 404.html if available."""
    custom = site_dir / "404.html"
    if custom.is_file():
        return FileResponse(path=custom, status_code=404, media_type="text/html")
    return Response(content="Not Found", status_code=404, media_type="text/plain")


def _is_within(path: Path, parent: Path) -> bool:
    """Check that path is inside parent (prevents directory traversal)."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
```

**Key behaviors:**
- Path traversal protection via `_is_within` check.
- Resolution order exactly mirrors kiln's `internal/server/server.go`.
- Separate `build_404` function so the app layer can call it when `resolve_file` returns `None`.

### 1.3 `src/forge_overlay/inject.py`

Injects the overlay `<script>` and `<link>` tags into HTML responses that contain `</head>`.

```python
from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The snippet injected before </head> in every HTML response.
SNIPPET = (
    '<link rel="stylesheet" href="/ops/ops.css">\n'
    '<script type="module" src="/ops/ops.js"></script>\n'
)


class InjectMiddleware:
    """ASGI middleware that injects overlay assets into HTML responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Buffer body chunks so we can inspect/modify the full body
        response_started = False
        initial_message: Message | None = None
        body_chunks: list[bytes] = []

        async def buffered_send(message: Message) -> None:
            nonlocal response_started, initial_message

            if message["type"] == "http.response.start":
                initial_message = message
                response_started = True
                return

            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

                if not message.get("more_body", False):
                    # Final chunk — process and send
                    assert initial_message is not None
                    full_body = b"".join(body_chunks)
                    headers = dict(initial_message.get("headers", []))

                    content_type = headers.get(b"content-type", b"").decode("latin-1", errors="replace")

                    if "text/html" in content_type:
                        full_body = _inject(full_body)
                        # Update content-length
                        new_headers = [
                            (k, v) for k, v in initial_message.get("headers", [])
                            if k.lower() != b"content-length"
                        ]
                        new_headers.append((b"content-length", str(len(full_body)).encode()))
                        initial_message["headers"] = new_headers

                    await send(initial_message)
                    await send({"type": "http.response.body", "body": full_body})

        await self.app(scope, receive, buffered_send)


def _inject(body: bytes) -> bytes:
    """Inject the overlay snippet before </head> if present."""
    marker = b"</head>"
    idx = body.lower().find(marker)
    if idx == -1:
        return body
    return body[:idx] + SNIPPET.encode() + body[idx:]
```

**Key points:**
- Buffers the full response body before deciding whether to inject. This is acceptable because HTML pages are small.
- Only injects into responses with `text/html` content type.
- Only injects if `</head>` is present (case-insensitive search).
- Updates `content-length` header after injection to prevent truncation.

### 1.4 `tests/conftest.py`

Shared fixtures for all tests.

```python
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from forge_overlay.config import Config


@pytest.fixture
def tmp_site(tmp_path: Path) -> Path:
    """Create a minimal site directory with test files."""
    # index page
    (tmp_path / "index.html").write_text(
        "<html><head></head><body>Home</body></html>"
    )
    # A nested page with clean URL support
    (tmp_path / "about.html").write_text(
        "<html><head></head><body>About</body></html>"
    )
    # A directory with index
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog" / "index.html").write_text(
        "<html><head></head><body>Blog</body></html>"
    )
    # Non-HTML asset
    (tmp_path / "style.css").write_text("body { margin: 0; }")
    # Custom 404
    (tmp_path / "404.html").write_text(
        "<html><head></head><body>Not Found</body></html>"
    )
    return tmp_path


@pytest.fixture
def tmp_overlay(tmp_path: Path) -> Path:
    """Create a minimal overlay assets directory."""
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "ops.js").write_text("// overlay JS")
    (overlay / "ops.css").write_text("/* overlay CSS */")
    return overlay


@pytest.fixture
def config(tmp_site: Path, tmp_overlay: Path) -> Config:
    """Config pointing at test fixtures."""
    return Config(site_dir=tmp_site, overlay_dir=tmp_overlay)
```

### 1.5 `tests/test_static_handler.py`

```python
from __future__ import annotations

from pathlib import Path

from forge_overlay.static_handler import resolve_file, build_response, build_404


class TestResolveFile:
    def test_root_resolves_to_index(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/")
        assert result is not None
        assert result.name == "index.html"

    def test_exact_file(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/style.css")
        assert result is not None
        assert result.name == "style.css"

    def test_clean_url_html_extension(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/about")
        assert result is not None
        assert result.name == "about.html"

    def test_directory_index(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/blog")
        assert result is not None
        assert result.name == "index.html"
        assert "blog" in str(result)

    def test_missing_file_returns_none(self, tmp_site: Path) -> None:
        assert resolve_file(tmp_site, "/nonexistent") is None

    def test_path_traversal_blocked(self, tmp_site: Path) -> None:
        assert resolve_file(tmp_site, "/../../../etc/passwd") is None


class TestBuild404:
    def test_custom_404(self, tmp_site: Path) -> None:
        resp = build_404(tmp_site)
        assert resp.status_code == 404

    def test_default_404(self, tmp_path: Path) -> None:
        resp = build_404(tmp_path)
        assert resp.status_code == 404
```

### 1.6 `tests/test_inject.py`

```python
from __future__ import annotations

from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from forge_overlay.inject import InjectMiddleware, SNIPPET


def _make_app(html_body: str = "<html><head></head><body>hi</body></html>"):
    async def homepage(request):
        return HTMLResponse(html_body)

    async def plain(request):
        return PlainTextResponse("not html")

    app = Starlette(routes=[
        Route("/", homepage),
        Route("/plain", plain),
    ])
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
```

### 1.7 Verification

```bash
uv run pytest tests/test_static_handler.py tests/test_inject.py -v
```

All tests should pass. The static handler correctly resolves clean URLs and the injection middleware adds overlay assets to HTML responses.

---

## M2 — Events + Proxy

### 2.1 `src/forge_overlay/events.py`

An in-memory SSE broker. The rebuild endpoint publishes events; connected clients receive them via SSE.

```python
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator


class EventBroker:
    """Pub/sub broker for server-sent events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def publish(self, data: str) -> None:
        """Send an event to all connected subscribers."""
        for queue in self._subscribers:
            queue.put_nowait(data)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Yield events as they arrive. Use as `async for event in broker.subscribe()`."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        finally:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
```

**Key points:**
- Each SSE client gets its own `asyncio.Queue`.
- `publish()` is synchronous and non-blocking (`put_nowait`).
- The `subscribe()` generator cleans up on disconnect via `finally`.
- No persistence — events are fire-and-forget, which matches the live-reload use case.

### 2.2 `src/forge_overlay/proxy.py`

Reverse proxy for `/api/*` requests to `obsidian-agent`.

```python
from __future__ import annotations

import httpx
from starlette.requests import Request
from starlette.responses import StreamingResponse

# Headers that should not be forwarded between client and upstream
HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})


async def proxy_request(request: Request, upstream: str, client: httpx.AsyncClient) -> StreamingResponse:
    """Forward a request to the upstream and stream the response back."""
    # Build upstream URL: replace the /api prefix with upstream base
    # request.path_params["path"] gives us everything after /api/
    path = request.path_params.get("path", "")
    url = f"{upstream.rstrip('/')}/api/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # Forward headers, stripping hop-by-hop
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP and k.lower() != "host"
    }

    body = await request.body()

    upstream_resp = await client.request(
        method=request.method,
        url=url,
        headers=headers,
        content=body,
        follow_redirects=False,
    )

    # Filter hop-by-hop from response headers
    resp_headers = {
        k: v for k, v in upstream_resp.headers.items()
        if k.lower() not in HOP_BY_HOP
    }

    return StreamingResponse(
        content=upstream_resp.aiter_bytes(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )
```

**Key points:**
- Forwards method, path (after `/api/`), query string, headers, and body.
- Strips hop-by-hop headers in both directions.
- Removes `Host` header so httpx sets the correct one for upstream.
- Streams the response body to avoid buffering large responses.
- The `httpx.AsyncClient` is passed in (created once in app startup, shared across requests).

### 2.3 `tests/test_events.py`

```python
from __future__ import annotations

import asyncio

import pytest

from forge_overlay.events import EventBroker


class TestEventBroker:
    async def test_publish_to_subscriber(self) -> None:
        broker = EventBroker()
        received: list[str] = []

        async def consumer():
            async for event in broker.subscribe():
                received.append(event)
                if len(received) >= 2:
                    break

        task = asyncio.create_task(consumer())
        # Let the consumer start
        await asyncio.sleep(0.01)

        broker.publish('{"type":"rebuilt"}')
        broker.publish('{"type":"rebuilt"}')

        await asyncio.wait_for(task, timeout=1.0)
        assert received == ['{"type":"rebuilt"}', '{"type":"rebuilt"}']

    async def test_no_subscribers(self) -> None:
        broker = EventBroker()
        # Should not raise
        broker.publish("test")
        assert broker.subscriber_count == 0

    async def test_subscriber_cleanup(self) -> None:
        broker = EventBroker()

        async def short_consumer():
            async for event in broker.subscribe():
                break  # Exit after first event

        task = asyncio.create_task(short_consumer())
        await asyncio.sleep(0.01)
        assert broker.subscriber_count == 1

        broker.publish("done")
        await asyncio.wait_for(task, timeout=1.0)
        # After the generator exits, subscriber should be cleaned up
        assert broker.subscriber_count == 0

    async def test_multiple_subscribers(self) -> None:
        broker = EventBroker()
        results_a: list[str] = []
        results_b: list[str] = []

        async def consumer(results: list[str]):
            async for event in broker.subscribe():
                results.append(event)
                break

        task_a = asyncio.create_task(consumer(results_a))
        task_b = asyncio.create_task(consumer(results_b))
        await asyncio.sleep(0.01)

        broker.publish("hello")
        await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)

        assert results_a == ["hello"]
        assert results_b == ["hello"]
```

### 2.4 `tests/test_proxy.py`

```python
from __future__ import annotations

import httpx
import pytest
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from forge_overlay.proxy import proxy_request


def _make_proxy_app(upstream_url: str) -> Starlette:
    """Create a minimal app with just the proxy route for testing."""
    client = httpx.AsyncClient()

    async def proxy_route(request: Request) -> JSONResponse:
        return await proxy_request(request, upstream_url, client)

    return Starlette(routes=[
        Route("/api/{path:path}", proxy_route, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
    ])


class TestProxy:
    """Proxy tests using httpx mock transport to simulate upstream."""

    async def test_forwards_get(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url).startswith("http://upstream:3000/api/vault/notes")
            return httpx.Response(200, json={"ok": True})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        # Build a minimal starlette app to test through
        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[
            Route("/api/{path:path}", proxy_route),
        ])

        test_client = TestClient(app)
        resp = test_client.get("/api/vault/notes")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    async def test_forwards_post_body(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            body = request.content
            return httpx.Response(201, content=body, headers={"content-type": "application/json"})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[
            Route("/api/{path:path}", proxy_route, methods=["POST"]),
        ])

        test_client = TestClient(app)
        resp = test_client.post("/api/vault/notes", json={"title": "test"})
        assert resp.status_code == 201

    async def test_forwards_query_string(self) -> None:
        async def mock_handler(request: httpx.Request) -> httpx.Response:
            assert "q=hello" in str(request.url)
            return httpx.Response(200, json={"results": []})

        transport = httpx.MockTransport(mock_handler)
        client = httpx.AsyncClient(transport=transport)

        async def proxy_route(request: Request):
            return await proxy_request(request, "http://upstream:3000", client)

        app = Starlette(routes=[
            Route("/api/{path:path}", proxy_route),
        ])

        test_client = TestClient(app)
        resp = test_client.get("/api/search?q=hello")
        assert resp.status_code == 200
```

### 2.5 Verification

```bash
uv run pytest tests/test_events.py tests/test_proxy.py -v
```

---

## M3 — App Wiring + Integration

### 3.1 `src/forge_overlay/app.py`

The application factory. Wires all routes, middleware, and shared state.

```python
from __future__ import annotations

import json

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from sse_starlette.sse import EventSourceResponse

from forge_overlay.config import Config
from forge_overlay.events import EventBroker
from forge_overlay.inject import InjectMiddleware
from forge_overlay.proxy import proxy_request
from forge_overlay.static_handler import build_404, build_response, resolve_file


def create_app(config: Config) -> Starlette:
    """Build and return the forge-overlay ASGI application."""
    broker = EventBroker()
    http_client = httpx.AsyncClient()

    # --- Route handlers ---

    async def rebuild_trigger(request: Request) -> Response:
        """POST /internal/rebuild — accept webhook from kiln-fork."""
        broker.publish(json.dumps({"type": "rebuilt"}))
        return Response(status_code=204)

    async def sse_events(request: Request) -> EventSourceResponse:
        """GET /ops/events — SSE stream for rebuild notifications."""
        async def event_generator():
            async for data in broker.subscribe():
                yield {"data": data}

        return EventSourceResponse(event_generator())

    async def overlay_static(request: Request) -> Response:
        """GET /ops/{path} — serve overlay assets (ops.js, ops.css)."""
        path = request.path_params.get("path", "")
        file_path = (config.overlay_dir / path).resolve()
        # Security: ensure file is within overlay_dir
        try:
            file_path.relative_to(config.overlay_dir.resolve())
        except ValueError:
            return Response("Forbidden", status_code=403)
        if not file_path.is_file():
            return Response("Not Found", status_code=404)
        return FileResponse(file_path)

    async def api_proxy(request: Request) -> Response:
        """ANY /api/{path} — reverse proxy to obsidian-agent."""
        return await proxy_request(request, config.api_upstream, http_client)

    async def site_static(request: Request) -> Response:
        """GET /{path} — serve site output with clean URLs."""
        url_path = request.url.path

        # Trailing-slash canonicalization: /foo/ -> /foo (except root)
        if url_path != "/" and url_path.endswith("/"):
            target = url_path.rstrip("/")
            if request.url.query:
                target = f"{target}?{request.url.query}"
            return RedirectResponse(url=target, status_code=301)

        resolved = resolve_file(config.site_dir, url_path)
        if resolved is None:
            return build_404(config.site_dir)
        return build_response(resolved)

    # --- App assembly ---

    routes = [
        Route("/internal/rebuild", rebuild_trigger, methods=["POST"]),
        Route("/ops/events", sse_events),
        Route("/ops/{path:path}", overlay_static),
        Route("/api/{path:path}", api_proxy, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]),
        Route("/{path:path}", site_static),
    ]

    app = Starlette(routes=routes)

    async def on_shutdown() -> None:
        await http_client.aclose()

    app.add_event_handler("shutdown", on_shutdown)

    # Wrap with injection middleware
    return InjectMiddleware(app)
```

**Key points:**
- `create_app(config)` is the single entrypoint — makes testing easy.
- The `EventBroker` and `httpx.AsyncClient` are created once and shared.
- The `httpx.AsyncClient` is closed on shutdown.
- `InjectMiddleware` wraps the entire app, so all HTML responses (including site pages and 404) get overlay assets injected.
- Route order matters: specific routes (`/internal/rebuild`, `/ops/*`, `/api/*`) are listed before the catch-all `/{path:path}`.
- Trailing-slash redirects happen at the route handler level (not middleware) to keep things simple.

### 3.2 `src/forge_overlay/main.py`

CLI entrypoint for running the server.

```python
from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from forge_overlay.app import create_app
from forge_overlay.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="forge-overlay development server")
    parser.add_argument("--site-dir", type=Path, default=os.environ.get("FORGE_SITE_DIR", "public"),
                        help="Path to site output directory (default: public)")
    parser.add_argument("--overlay-dir", type=Path, default=os.environ.get("FORGE_OVERLAY_DIR", "overlay"),
                        help="Path to overlay assets directory (default: overlay)")
    parser.add_argument("--api-upstream", type=str, default=os.environ.get("FORGE_API_UPSTREAM", "http://127.0.0.1:3000"),
                        help="Upstream URL for /api/* proxy (default: http://127.0.0.1:3000)")
    parser.add_argument("--host", type=str, default=os.environ.get("FORGE_HOST", "127.0.0.1"),
                        help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("FORGE_PORT", "8080")),
                        help="Bind port (default: 8080)")
    args = parser.parse_args()

    config = Config(
        site_dir=Path(args.site_dir),
        overlay_dir=Path(args.overlay_dir),
        api_upstream=args.api_upstream,
        host=args.host,
        port=args.port,
    )

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
```

**Key points:**
- CLI args take precedence over environment variables, which take precedence over defaults.
- Environment variable names use `FORGE_` prefix for namespacing.
- `uvicorn.run()` is called directly — no need for a separate config file.

### 3.3 `tests/test_integration.py`

End-to-end test verifying the rebuild webhook -> SSE pipeline.

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

from forge_overlay.app import create_app
from forge_overlay.config import Config


class TestRebuildToSSE:
    """Integration test: POST /internal/rebuild triggers SSE event on /ops/events."""

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
        # Injection should have added overlay assets
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
        # Even 404 gets injection
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
        assert "ops.js" not in resp.text  # No injection for CSS
```

### 3.4 Verification

```bash
uv run pytest -v
```

All tests across all files should pass.

---

## M4 — Readiness

### 4.1 Run Full Test Suite

```bash
uv run pytest -v --cov=forge_overlay --cov-report=term-missing
```

Target: all tests pass, reasonable coverage of the core paths.

### 4.2 Run Linter and Type Checker

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/forge_overlay/
```

Fix any issues found. Common things to expect:
- Missing type annotations on test functions (can ignore or add `-> None`)
- ruff import ordering issues (auto-fixable with `ruff check --fix`)

### 4.3 Manual Smoke Test (with kiln-fork)

Prerequisites: `kiln-fork` binary available, an Obsidian vault, and a built site.

```bash
# Terminal 1: Start the overlay server
uv run forge-overlay --site-dir ./public --overlay-dir ./overlay

# Terminal 2: Start kiln-fork in watch mode
kiln dev --no-serve --on-rebuild http://127.0.0.1:8080/internal/rebuild --input ./vault --output ./public

# Terminal 3: Connect to SSE and watch for events
curl -N http://127.0.0.1:8080/ops/events

# Terminal 4: Edit a file in the vault to trigger a rebuild
echo "test" >> ./vault/test.md
# Expect: kiln rebuilds -> POST /internal/rebuild -> SSE event appears in terminal 3
```

### 4.4 Manual Smoke Test (standalone, no kiln-fork)

```bash
# Terminal 1: Start with a test site
mkdir -p /tmp/test-site /tmp/test-overlay
echo '<html><head></head><body>Hello</body></html>' > /tmp/test-site/index.html
echo '// ops' > /tmp/test-overlay/ops.js
echo '/* ops */' > /tmp/test-overlay/ops.css

uv run forge-overlay --site-dir /tmp/test-site --overlay-dir /tmp/test-overlay

# Terminal 2: Verify site serving + injection
curl http://127.0.0.1:8080/
# Expect: HTML with injected ops.js and ops.css tags

# Trigger rebuild manually
curl -X POST http://127.0.0.1:8080/internal/rebuild -H "Content-Type: application/json" -d '{"type":"rebuilt"}'
# Expect: 204 response
```

---

## Reference: Route Table

| Method | Path                    | Handler            | Description                        |
|--------|-------------------------|--------------------|------------------------------------|
| POST   | `/internal/rebuild`     | `rebuild_trigger`  | Accept kiln-fork webhook           |
| GET    | `/ops/events`           | `sse_events`       | SSE stream for rebuild events      |
| GET    | `/ops/{path}`           | `overlay_static`   | Serve overlay assets               |
| ANY    | `/api/{path}`           | `api_proxy`        | Reverse proxy to obsidian-agent    |
| GET    | `/{path}`               | `site_static`      | Serve site output + HTML injection |

## Reference: kiln-fork Integration

**Command:**
```bash
kiln dev --no-serve --on-rebuild http://127.0.0.1:8080/internal/rebuild --input <vault> --output <public>
```

**Contract:**
- `--no-serve`: kiln builds and watches but does not serve (overlay handles serving)
- `--on-rebuild <url>`: kiln POSTs `{"type":"rebuilt"}` to this URL after each rebuild
- Webhook POST timeout: 5 seconds, failures logged but non-fatal
- Initial full build does NOT emit a webhook; only file-change rebuilds do
- `Content-Type: application/json`

## Reference: Environment Variables

| Variable              | Default                    | Description                     |
|-----------------------|----------------------------|---------------------------------|
| `FORGE_SITE_DIR`      | `public`                   | Site output directory           |
| `FORGE_OVERLAY_DIR`   | `overlay`                  | Overlay assets directory        |
| `FORGE_API_UPSTREAM`  | `http://127.0.0.1:3000`   | obsidian-agent upstream URL     |
| `FORGE_HOST`          | `127.0.0.1`               | Bind host                       |
| `FORGE_PORT`          | `8080`                     | Bind port                       |
