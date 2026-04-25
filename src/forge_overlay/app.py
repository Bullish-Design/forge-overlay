from __future__ import annotations

import json
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, RedirectResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp

from forge_overlay.config import Config
from forge_overlay.events import EventBroker
from forge_overlay.inject import InjectMiddleware
from forge_overlay.proxy import proxy_request
from forge_overlay.static_handler import build_404, build_response, resolve_file


def create_app(config: Config) -> ASGIApp:
    """Build and return the forge-overlay ASGI application."""
    broker = EventBroker()
    http_client = httpx.AsyncClient()

    async def rebuild_trigger(_request: Request) -> Response:
        """POST /internal/rebuild - accept webhook from kiln-fork."""
        broker.publish(json.dumps({"type": "rebuilt"}))
        return Response(status_code=204)

    async def sse_events(_request: Request) -> EventSourceResponse:
        """GET /ops/events - SSE stream for rebuild notifications."""

        async def event_generator() -> AsyncGenerator[dict[str, str]]:
            async for data in broker.subscribe():
                yield {"data": data}

        return EventSourceResponse(event_generator())

    async def overlay_static(request: Request) -> Response:
        """GET /ops/{path} - serve overlay assets (ops.js, ops.css)."""
        path = request.path_params.get("path", "")
        file_path = (config.overlay_dir / path).resolve()

        try:
            file_path.relative_to(config.overlay_dir.resolve())
        except ValueError:
            return Response("Forbidden", status_code=403)
        if not file_path.is_file():
            return Response("Not Found", status_code=404)
        return FileResponse(file_path)

    async def api_proxy(request: Request) -> Response:
        """ANY /api/{path} - reverse proxy to obsidian-agent."""
        return await proxy_request(request, config.api_upstream, http_client)

    async def site_static(request: Request) -> Response:
        """GET /{path} - serve site output with clean URLs."""
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

    routes = [
        Route("/internal/rebuild", rebuild_trigger, methods=["POST"]),
        Route("/ops/events", sse_events),
        Route("/ops/{path:path}", overlay_static),
        Route(
            "/api/{path:path}",
            api_proxy,
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
        ),
        Route("/{path:path}", site_static),
    ]

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await http_client.aclose()

    app = Starlette(routes=routes, lifespan=lifespan)
    return InjectMiddleware(app)
