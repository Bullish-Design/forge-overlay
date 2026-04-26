# Testing Analysis - forge-overlay

Date: 2026-04-25

## Current Verification Snapshot

1. Automated checks currently pass in `devenv`:
1. `uv run pytest -v --cov=forge_overlay --cov-report=term-missing`
1. `uv run mypy src/forge_overlay/`
1. `uv run ruff check src tests`
1. `uv run ruff format --check src tests`
1. Current coverage result: `81%` total (`26` tests passing).

## Coverage by Module

1. `src/forge_overlay/main.py`: `0%` coverage. CLI/env parsing and `uvicorn.run()` wiring are untested.
1. `src/forge_overlay/app.py`: `80%` coverage. Missing routes/branches and lifecycle paths.
1. `src/forge_overlay/static_handler.py`: `87%` coverage. Error branches and edge-path handling are partially untested.
1. `src/forge_overlay/inject.py`: `95%` coverage. `non-http` scope passthrough branch is untested.
1. `src/forge_overlay/events.py`, `proxy.py`, `config.py`: functionally covered for current happy-path behavior.

## What Is Good Today

1. Static URL resolution behavior is tested (`/`, clean URLs, directory index, missing page).
1. HTML injection behavior is tested for standard HTML and non-HTML response types.
1. Event broker fan-out and subscriber cleanup behavior is tested.
1. Proxy GET/POST/query forwarding is tested with `httpx.MockTransport`.
1. App-level route smoke checks exist for rebuild endpoint, static serving, and redirects.

## Gaps Blocking Full Verification

1. No CLI tests for argument precedence (`CLI > env > default`) in `main.py`.
1. No direct SSE integration assertion that a `POST /internal/rebuild` produces a stream event on `/ops/events`.
1. No tests for `/ops/{path}` traversal defense (`403`) and missing file behavior (`404`) at app level.
1. No tests for proxy header policy (hop-by-hop strip, `Host` removal, response header filtering).
1. No tests for upstream proxy failures (timeout/connect errors) and expected API-facing behavior.
1. No tests proving app lifespan cleanup closes the shared `httpx.AsyncClient`.
1. No failure threshold in coverage policy (`--cov-fail-under` absent), so regressions can land while still "passing".
1. Coverage run emits `module-not-measured` warning, so coverage signal quality is noisy.

## Risk Assessment

1. Highest risk: regressions in startup/runtime behavior (`main.py`) and unhandled proxy failure modes.
1. Medium risk: event delivery contract and overlay static security branches.
1. Lower risk: already-covered happy paths in static/injection/proxy forwarding.

## Bottom Line

Current tests are a strong baseline but not full verification. This repository needs targeted test refactoring and additional branch/failure coverage before it can be considered fully verified.
