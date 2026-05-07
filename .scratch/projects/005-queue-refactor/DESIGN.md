# Design

Updated: 2026-04-27

## Context

`forge-overlay` is the browser-facing transport layer for Forge. The upcoming queue refactor expands the proxy contract so browser clients can submit jobs, poll status, and optionally subscribe to streaming updates from `obsidian-agent`.

The overlay should remain an edge service:
- It forwards requests and responses
- It preserves browser-friendly semantics
- It does not own queue scheduling or job state

## Responsibility Boundary

`forge-overlay` must:
- Proxy queue/job endpoints under `/api/*`
- Map upstream failures into stable client-facing error shapes
- Support long-running requests without forcing the browser into a blocking UX
- Relay SSE or websocket-style status streams when the upstream exposes them
- Preserve enough headers, status, and timing data for debugging

`forge-overlay` must not:
- Store queued jobs
- Reconcile or mutate job state
- Retry or reschedule work on behalf of `obsidian-agent`

## Queue Contract

Expected lifecycle:
1. Browser submits a job through the overlay proxy.
2. `obsidian-agent` returns quickly with a `job_id` or equivalent handle.
3. Browser polls a status endpoint or subscribes to an event stream.
4. Overlay forwards updates with minimal transformation.

Expected failure mapping:
- Upstream timeout -> `upstream_timeout`
- Upstream connection or availability failure -> `upstream_unavailable`
- Upstream semantic errors -> preserve upstream status where practical

## Architecture

Primary route behavior:
- `ANY /api/{path:path}`: proxy queue/job requests to `obsidian-agent`
- `GET /api/{path:path}` for status polling: forward transparently
- Optional SSE/websocket bridge: pass through streaming status if the upstream exposes it
- Observability hooks: log request id, `job_id`, upstream status, and elapsed time

Design constraints:
- Prefer non-blocking job flows over synchronous wait patterns
- Keep proxy timeouts configurable
- Avoid buffering streaming responses unnecessarily
- Do not expose sensitive payloads in logs

## Decisions

1. Keep the overlay proxy-only for queue behavior.
2. Treat job submission as a fast acknowledgement path with follow-up polling or streaming.
3. Preserve upstream status codes whenever they still communicate useful job failure state.
4. Map transport failures to stable overlay errors so browser clients do not depend on raw `httpx` exceptions.
5. Keep streaming support optional and feature-detected rather than hard-required.

## Assumptions

1. `obsidian-agent` will expose stable async job endpoints under `/api/*`.
2. Streaming support, if present, may be SSE or websocket-based.
3. Browser clients will continue to use the overlay as the public entry point.
4. The queue implementation lives outside this repository and may evolve independently.
