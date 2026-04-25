from __future__ import annotations

import httpx
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse

# Headers that should not be forwarded between client and upstream
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    }
)


async def proxy_request(
    request: Request, upstream: str, client: httpx.AsyncClient
) -> StreamingResponse | Response:
    """Forward a request to the upstream and stream the response back."""
    path = request.path_params.get("path", "")
    url = f"{upstream.rstrip('/')}/api/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP and k.lower() != "host"}

    body = await request.body()

    try:
        upstream_resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            follow_redirects=False,
        )
    except httpx.HTTPError:
        return Response(
            content='{"error":"upstream_unavailable"}',
            status_code=502,
            media_type="application/json",
        )

    resp_headers = {k: v for k, v in upstream_resp.headers.items() if k.lower() not in HOP_BY_HOP}

    return StreamingResponse(
        content=upstream_resp.aiter_bytes(),
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )
