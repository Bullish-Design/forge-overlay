# FORGE_OVERLAY_REFACTOR_GUIDE

## Purpose
Align `forge-overlay` with the refactored `obsidian-agent` job/queue API so browser clients can use async job workflows (`submit -> poll/list`) without direct access to the agent host.

This guide is based on:
- `obsidian-agent` at `/home/andrew/Documents/Projects/obsidian-agent`
- `forge-overlay` at `/home/andrew/Documents/Projects/forge-overlay`

Assumptions explicitly accepted for this scope:
- Ignore cancellation.
- Ignore durable queue persistence/restart recovery.
- Ignore retry/idempotency policy.

## Current State Summary

### Obsidian-Agent (already refactored)
Implemented and validated:
- Queue-backed lifecycle for mutation operations (`queued`, `running`, `succeeded`, `failed`).
- Async job endpoints:
  - `POST /v1/jobs`
  - `GET /v1/jobs/{job_id}`
  - `GET /v1/jobs?limit=...`
- Compatibility endpoints still exist and now run through queue:
  - `POST /api/agent/apply`
  - `POST /api/agent/undo`
- App tests pass for queue + app behavior.

### Forge-Overlay (current gap)
- Only proxies `/api/{path}` to upstream `/api/{path}`.
- Does **not** proxy `/v1/*`.
- Browser requests to `/v1/jobs*` currently fall through static routing and fail.
- Proxy timeout/error behavior is currently coarse in repo source:
  - catches `httpx.HTTPError` -> `502 {"error":"upstream_unavailable"}`
  - no distinct timeout error payload in this repo source.

## Required Refactor

## 1) Add Upstream Proxy Support for `/v1/*` (Critical)

Problem:
- Refactored agent exposes async jobs under `/v1/jobs*`.
- Overlay only forwards `/api/*` today.

Required changes:
- Add overlay route for `/v1/{path:path}` in `src/forge_overlay/app.py`.
- Route should proxy to upstream `/v1/{path}`.
- Preserve query strings and request method/body/headers like existing `/api/*` path.

Implementation approach:
- Generalize proxy helper to accept an upstream base path prefix.
- Reuse same hop-by-hop header stripping and streaming response behavior.

Suggested API in `proxy.py`:
- Keep existing `proxy_request(...)` for backward compatibility, or replace with:
  - `proxy_request(request, upstream, client, upstream_prefix="/api")`
  - For `/api/{path}` call with `upstream_prefix="/api"`
  - For `/v1/{path}` call with `upstream_prefix="/v1"`

Acceptance criteria:
- `GET /v1/jobs` via overlay reaches upstream `/v1/jobs`.
- `POST /v1/jobs` via overlay returns 202 and job payload.
- `GET /v1/jobs/{id}` via overlay returns live job status.

## 2) Preserve `/api/*` Compatibility (Critical)

Problem:
- Existing clients still rely on `/api/agent/apply` and `/api/agent/undo`.

Required changes:
- Keep current `/api/{path}` proxy route unchanged in behavior for successful requests.
- Ensure no regressions in existing test suite expectations for `/api/*` forwarding.

Acceptance criteria:
- Existing `/api/*` tests continue passing.
- Compatibility flows still operational for synchronous-style clients.

## 3) Improve Proxy Error Semantics (High)

Why now:
- Queue workflows involve polling and long-running operations.
- Distinguishing timeout vs generic upstream failure improves UI behavior and diagnostics.

Required changes:
- In `src/forge_overlay/proxy.py`, map timeout exceptions separately:
  - `httpx.TimeoutException` -> `504` with `{"error":"upstream_timeout"}`
- Keep generic upstream failures:
  - `httpx.HTTPError` -> `502` with `{"error":"upstream_unavailable"}`

Notes:
- This is compatible with current agent behavior and useful for queue polling UX.
- Continue passing through upstream HTTP status codes when upstream responds successfully (including non-2xx).

Acceptance criteria:
- Timeout path returns 504/`upstream_timeout`.
- Connect/read/protocol failures continue returning 502/`upstream_unavailable`.
- Upstream 4xx/5xx responses are streamed through unchanged.

## 4) Add Configurable Proxy Timeout to Overlay Repo Source (High)

Problem:
- This repo’s `forge-overlay` source currently creates `httpx.AsyncClient()` without configured timeout.
- Long operations and queue polling should use explicit timeout policy.

Required changes:
- In `src/forge_overlay/config.py` add:
  - `api_proxy_timeout_s: float = 600.0`
- In `src/forge_overlay/main.py` add CLI/env wiring:
  - `--api-proxy-timeout-s`
  - env `FORGE_API_PROXY_TIMEOUT_S`
- In `src/forge_overlay/app.py` create client with:
  - `httpx.AsyncClient(timeout=httpx.Timeout(config.api_proxy_timeout_s))`

Acceptance criteria:
- `forge-overlay --help` shows timeout option with default.
- Runtime client uses configured timeout.

## 5) Update Tests for New `/v1/*` Surface (Critical)

Files to update/add:
- `tests/test_proxy.py`
- `tests/test_integration.py`

Minimum new test cases:
1. Forwards `GET /v1/jobs?limit=10` to upstream `/v1/jobs?limit=10`.
2. Forwards `POST /v1/jobs` body unchanged.
3. Forwards `GET /v1/jobs/{id}`.
4. Timeout error mapping returns 504 + `upstream_timeout`.
5. Generic upstream error mapping remains 502 + `upstream_unavailable`.
6. Existing `/api/*` forwarding tests remain green.

Implementation note:
- Update `_build_app(...)` helper in proxy tests to mount both `/api/{path}` and `/v1/{path}` routes when needed.

## 6) Update Documentation (Medium)

Update `README.md` in `forge-overlay` with:
- Refreshed API edge surface:
  - Proxies both `/api/*` and `/v1/*`.
- Job API examples through overlay:
  - `POST /v1/jobs`
  - `GET /v1/jobs/{job_id}`
  - `GET /v1/jobs?limit=...`
- Proxy timeout option docs:
  - CLI flag and env var.
- Error mapping contract:
  - `upstream_timeout` (504)
  - `upstream_unavailable` (502)

## File-Level Change List

1. `src/forge_overlay/config.py`
- Add `api_proxy_timeout_s` to `Config` dataclass.

2. `src/forge_overlay/main.py`
- Add Typer option/env for `api_proxy_timeout_s`.
- Pass into `Config(...)`.

3. `src/forge_overlay/app.py`
- Construct `httpx.AsyncClient` with configured timeout.
- Add route handler for `/v1/{path:path}`.
- Ensure `/api/*` and `/v1/*` both call proxy utility with correct upstream prefix.

4. `src/forge_overlay/proxy.py`
- Add path-prefix-aware proxy builder.
- Add timeout-specific exception mapping.
- Keep header filtering/stream behavior unchanged.

5. `tests/test_proxy.py`
- Extend route coverage to `/v1/*`.
- Update timeout expectation (504/upstream_timeout).

6. `tests/test_integration.py`
- Add overlay-level coverage for `/v1/jobs*` route wiring.

7. `README.md`
- Document new proxy surface and runtime knobs.

## Migration/Rollout Plan

1. Implement route + proxy helper generalization (`/v1/*` support).
2. Add timeout config + CLI/env plumbing.
3. Update proxy error mapping.
4. Update and run tests.
5. Update README.
6. Validate against live `obsidian-agent`:
   - Submit job through overlay, poll status, list recent jobs.

## End-to-End Validation Checklist

- [ ] `forge-overlay --help` includes `--api-proxy-timeout-s` and env var.
- [ ] `POST /v1/jobs` through overlay returns 202 + `job_id`.
- [ ] `GET /v1/jobs/{job_id}` through overlay returns valid lifecycle status.
- [ ] `GET /v1/jobs?limit=10` through overlay returns jobs array.
- [ ] `POST /api/agent/apply` still works unchanged through overlay.
- [ ] Timeout faults return `504 {"error":"upstream_timeout"}`.
- [ ] Non-timeout upstream transport faults return `502 {"error":"upstream_unavailable"}`.
- [ ] Test suite passes for updated proxy + integration coverage.

## Non-Goals for This Refactor

- Implementing cancellation routes/status.
- Implementing durable queue state in overlay.
- Implementing retry/idempotency logic in overlay.
- Implementing UI queue rendering (that belongs in Forge UI repo layer).

## Risk Notes

- Route precedence: ensure `/v1/{path}` proxy route is evaluated before static catch-all route `/{path:path}`.
- Header handling: preserve host/header filtering to avoid leaking client host headers upstream.
- Backward compatibility: keep `/api/*` behavior stable while adding `/v1/*`.

## Definition of Done

Refactor is complete when forge-overlay can transparently proxy both legacy `/api/*` and job-oriented `/v1/*` obsidian-agent APIs, with explicit timeout semantics and updated tests/docs.
