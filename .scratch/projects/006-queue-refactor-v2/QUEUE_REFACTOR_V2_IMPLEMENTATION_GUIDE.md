# QUEUE_REFACTOR_V2_IMPLEMENTATION_GUIDE

## Objective
Implement the `forge-overlay` refactor described in `FORGE_OVERLAY_REFACTOR_GUIDE.md` so overlay supports both legacy `/api/*` and queue/job `/v1/*` upstream APIs, with explicit timeout behavior and updated tests/docs.

## Scope and Non-Goals
In scope:
- Add `/v1/*` proxy support.
- Preserve `/api/*` behavior.
- Add timeout config + CLI/env wiring.
- Improve timeout vs generic upstream error mapping.
- Update tests and README.

Out of scope:
- Cancellation.
- Persistent queue state.
- Retry/idempotency policy.

## Current Code Reality (Confirmed)
- `src/forge_overlay/app.py` only proxies `Route("/api/{path:path}")`.
- `src/forge_overlay/proxy.py` hardcodes upstream path as `/api/{path}`.
- `src/forge_overlay/proxy.py` maps all `httpx.HTTPError` to `502 {"error":"upstream_unavailable"}`.
- `src/forge_overlay/app.py` builds `httpx.AsyncClient()` with no configured timeout.
- `src/forge_overlay/config.py` has no `api_proxy_timeout_s`.
- `src/forge_overlay/main.py` has no `--api-proxy-timeout-s` / `FORGE_API_PROXY_TIMEOUT_S`.
- `README.md` is minimal and does not document proxy behavior.

## Implementation Plan (Step-by-Step)

### 1. Create a branch and snapshot baseline
1. Create branch:
   - `git checkout -b queue-refactor-v2-overlay`
2. Run baseline tests so regressions are obvious later:
   - `pytest -q`
3. Record current failures (if any) before changing code.

### 2. Extend runtime config with proxy timeout
File: `src/forge_overlay/config.py`

1. Add field to `Config` dataclass:
   - `api_proxy_timeout_s: float = 600.0`
2. Add a concise comment indicating this timeout applies to upstream proxy calls (`/api/*` and `/v1/*`).

Acceptance check:
- `Config()` should still construct with defaults.
- Existing fixtures in `tests/conftest.py` should continue working without modification (dataclass default handles this).

### 3. Wire timeout through CLI and env
File: `src/forge_overlay/main.py`

1. Add Typer option argument:
   - Name: `api_proxy_timeout_s`
   - CLI flag: `--api-proxy-timeout-s`
   - Env var: `FORGE_API_PROXY_TIMEOUT_S`
   - Type: `float`
   - Default: `600.0`
   - Help text should explicitly say it controls upstream API proxy timeout in seconds.
2. Pass this into `Config(...)` when building config.

Tests to update in same step:
- `tests/test_main.py`

Required edits:
1. In `test_defaults_with_no_args_or_env`, assert `config.api_proxy_timeout_s == 600.0`.
2. In `test_env_vars_override_defaults`, add env override and assert parsed float.
3. In `test_cli_flags_override_env_vars`, include CLI flag override and assert CLI wins.
4. Keep `test_uvicorn_receives_config_values` behavior unchanged (timeout is for app config, not uvicorn args).

Acceptance check:
- `pytest tests/test_main.py -q` passes.
- `python -m forge_overlay.main --help` displays `--api-proxy-timeout-s` and env var binding.

### 4. Generalize proxy function to support both `/api` and `/v1`
File: `src/forge_overlay/proxy.py`

1. Change function signature from:
   - `proxy_request(request, upstream, client)`
   to:
   - `proxy_request(request, upstream, client, upstream_prefix="/api")`
2. Build upstream URL using provided prefix:
   - `url = f"{upstream.rstrip('/')}{upstream_prefix}/{path}"`
   - Preserve query string behavior exactly as now.
3. Keep existing request-header filtering behavior (`HOP_BY_HOP` + drop `host`).
4. Keep existing response header filtering and streaming behavior.

Important detail:
- Normalize `upstream_prefix` to ensure exactly one leading slash and no trailing slash to avoid malformed URLs.

Acceptance checks:
- Existing `/api` tests should continue to pass when no explicit prefix argument is supplied.
- New `/v1` route can pass `upstream_prefix="/v1"`.

### 5. Improve error mapping semantics
File: `src/forge_overlay/proxy.py`

1. Add dedicated timeout exception handling before generic HTTP error handling:
   - `except httpx.TimeoutException:` -> `504` + JSON `{"error":"upstream_timeout"}`
2. Keep generic upstream transport failure mapping:
   - `except httpx.HTTPError:` -> `502` + JSON `{"error":"upstream_unavailable"}`
3. Do not change pass-through behavior for upstream responses (including 4xx/5xx).

Acceptance checks:
- Read timeout path yields 504 timeout payload.
- Connect/protocol errors still yield 502 unavailable payload.
- Upstream non-2xx still stream through unchanged status/body.

### 6. Add `/v1/*` route wiring in app
File: `src/forge_overlay/app.py`

1. Construct HTTP client with configured timeout:
   - `httpx.AsyncClient(timeout=httpx.Timeout(config.api_proxy_timeout_s))`
2. Split proxy handlers into two explicit handlers (recommended for readability):
   - `api_proxy` calls `proxy_request(..., upstream_prefix="/api")`
   - `v1_proxy` calls `proxy_request(..., upstream_prefix="/v1")`
3. Add route for `/v1/{path:path}` with same method set as `/api/{path:path}`.
4. Ensure route order places `/v1/{path:path}` before static catch-all `/{path:path}` so v1 calls never fall through to static files.

Tests to update in same step:
- `tests/test_integration.py`

Required additions:
1. Add test similar to existing `test_api_proxy_route` for `GET /v1/jobs` and assert `proxy_request` was invoked with `/v1` prefix.
2. Keep the current `/api` proxy route test passing to prove compatibility.

Acceptance checks:
- `GET /v1/jobs` hits proxy route, not static 404.
- `POST /v1/jobs` accepted by route (method coverage parity with `/api/*`).

### 7. Expand proxy unit tests for `/v1` and timeout semantics
File: `tests/test_proxy.py`

1. Update helper `_build_app(...)`:
   - Add both routes (`/api/{path:path}` and `/v1/{path:path}`), each calling `proxy_request` with explicit prefix.
   - Keep ability to vary methods.
2. Add new tests:
   - Forward `GET /v1/jobs?limit=10` to `http://upstream:3000/v1/jobs?limit=10`.
   - Forward `POST /v1/jobs` body unchanged.
   - Forward `GET /v1/jobs/{id}` unchanged.
3. Update timeout expectation test:
   - Rename or adjust `test_upstream_timeout_returns_502` to expect `504` + `{"error":"upstream_timeout"}`.
4. Keep generic error test expecting `502` + `{"error":"upstream_unavailable"}`.
5. Keep hop-by-hop and host-header behavior tests green.

Acceptance checks:
- `pytest tests/test_proxy.py -q` passes with both `/api` and `/v1` coverage.

### 8. Add integration coverage for route precedence and v1 forwarding
File: `tests/test_integration.py`

Add cases:
1. `/v1/jobs` calls proxy function (monkeypatched) and returns proxied payload.
2. `/v1/jobs?limit=10` preserves query string.
3. Optional but useful regression guard: requesting `/v1/something` should never return site 404 when proxy function is monkeypatched to return 200.

Acceptance checks:
- `pytest tests/test_integration.py -q` passes.
- Confirms `/v1/*` doesn’t leak into static route.

### 9. Update README documentation
File: `README.md`

Replace minimal README with concise operational docs:
1. Purpose and architecture summary.
2. Proxied surfaces:
   - `/api/*` -> upstream `/api/*`
   - `/v1/*` -> upstream `/v1/*`
3. Job API examples through overlay:
   - `POST /v1/jobs`
   - `GET /v1/jobs/{job_id}`
   - `GET /v1/jobs?limit=10`
4. Runtime config table including:
   - `--api-upstream` / `FORGE_API_UPSTREAM`
   - `--api-proxy-timeout-s` / `FORGE_API_PROXY_TIMEOUT_S`
5. Error contract:
   - `504 {"error":"upstream_timeout"}` for timeout exceptions.
   - `502 {"error":"upstream_unavailable"}` for other transport errors.

Acceptance checks:
- README examples match implemented route behavior and CLI names exactly.

### 10. Full validation pass
Run:
1. `pytest -q`
2. `python -m forge_overlay.main --help`

Manual smoke test against running upstream:
1. Start upstream agent locally.
2. Start overlay.
3. Submit job through overlay:
   - `curl -i -X POST http://127.0.0.1:8080/v1/jobs -H 'content-type: application/json' -d '{...}'`
4. Poll job:
   - `curl -i http://127.0.0.1:8080/v1/jobs/<job_id>`
5. List jobs:
   - `curl -i 'http://127.0.0.1:8080/v1/jobs?limit=10'`
6. Verify legacy compatibility still works:
   - `curl -i -X POST http://127.0.0.1:8080/api/agent/apply ...`

Expected outcomes:
- `/v1/jobs*` works through overlay.
- `/api/*` unchanged.
- Timeout and generic transport faults return correct mapped errors.

### 11. PR checklist for the intern
- [ ] Added `api_proxy_timeout_s` to config.
- [ ] Added CLI/env timeout wiring in `main.py`.
- [ ] `httpx.AsyncClient` uses configured timeout.
- [ ] Added `/v1/{path:path}` route.
- [ ] Generalized proxy function to accept upstream prefix.
- [ ] Timeout mapped to 504 `upstream_timeout`.
- [ ] Generic transport errors mapped to 502 `upstream_unavailable`.
- [ ] Updated `tests/test_main.py`.
- [ ] Updated `tests/test_proxy.py` with `/v1` and timeout semantics.
- [ ] Updated `tests/test_integration.py` for `/v1` routing.
- [ ] Updated README docs.
- [ ] `pytest -q` passes.

## Suggested Commit Breakdown
Use small commits to simplify review:
1. `config+cli`: timeout config and CLI/env wiring + `test_main` updates.
2. `proxy-core`: proxy prefix support + timeout mapping + proxy tests.
3. `app-routing`: `/v1/*` route + client timeout usage + integration tests.
4. `docs`: README update.

## Common Pitfalls to Avoid
- Adding `/v1/*` route after `/{path:path}` (will break routing).
- Catching `HTTPError` before `TimeoutException` (timeout will never map to 504).
- Forgetting to preserve query strings.
- Accidentally changing `/api/*` behavior while refactoring.
- Updating tests to match wrong behavior instead of fixing behavior.

## Definition of Done
Done when overlay transparently proxies both `/api/*` and `/v1/*`, uses configurable timeout, returns distinct timeout/unavailable errors, and updated tests/docs all pass.
