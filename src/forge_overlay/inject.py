from __future__ import annotations

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
        initial_message: Message | None = None
        body_chunks: list[bytes] = []

        async def buffered_send(message: Message) -> None:
            nonlocal initial_message

            if message["type"] == "http.response.start":
                initial_message = message
                return

            if message["type"] == "http.response.body":
                body_chunks.append(message.get("body", b""))

                if not message.get("more_body", False):
                    # Final chunk - process and send
                    assert initial_message is not None
                    full_body = b"".join(body_chunks)

                    start_headers = initial_message.get("headers", [])
                    content_type = ""
                    for k, v in start_headers:
                        if k.lower() == b"content-type":
                            content_type = v.decode("latin-1", errors="replace")
                            break

                    if "text/html" in content_type:
                        full_body = _inject(full_body)
                        # Update content-length
                        new_headers = [
                            (k, v) for k, v in start_headers if k.lower() != b"content-length"
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
