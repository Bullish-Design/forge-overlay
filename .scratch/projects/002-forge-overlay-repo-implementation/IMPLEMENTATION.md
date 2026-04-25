# Implementation

Updated: 2026-04-25

## Objective

Deliver a complete `forge-overlay` service from this template repo.

## Phased Plan

## M0 Bootstrap

1. Align `pyproject.toml` to `src/forge_overlay`
2. Add runtime deps: `starlette`, `sse-starlette`, `httpx`, `uvicorn[standard]`
3. Add test deps: `pytest-asyncio`, `anyio`
4. Create package and test scaffolding
5. Capture kiln-fork integration command in docs and examples:
   `kiln dev --no-serve --on-rebuild http://127.0.0.1:8080/internal/rebuild --input <vault> --output <public>`

## M1 Static + Injection

1. Implement `static_handler.py` clean URL and 404 behavior
2. Match kiln clean-URL behavior from `internal/server/server.go`:
   exact file, `<path>.html`, directory `index.html`, custom `404.html`
3. Implement trailing-slash canonicalization (`/path/` -> `/path`)
4. Implement `inject.py` middleware
5. Add focused unit tests for HTML and non-HTML responses

## M2 Events + Proxy

1. Implement `events.py` SSE broker
2. Implement `/ops/events` endpoint adapter
3. Implement `proxy.py` for `/api/*`
4. Implement `POST /internal/rebuild` trigger endpoint (non-blocking, 204 response)
5. Add unit tests for SSE and proxy behavior
6. Add unit tests that rebuild trigger emits `{"type":"rebuilt"}`

## M3 App Wiring + Integration

1. Implement `config.py`
2. Wire app routes in `app.py`
3. Add runtime entrypoint in `main.py`
4. Add integration test for `/internal/rebuild` -> SSE message
5. Add manual verification recipe with real kiln-fork:
   run `kiln dev --no-serve --on-rebuild ...`, edit vault file, verify SSE event arrives

## M4 Readiness

1. Run tests and fix defects
2. Run lint/type checks if configured
3. Update top-level run/test docs in repo
4. Document kiln-fork docs drift note:
   `docs/Commands/dev.md` currently omits `--no-serve` and `--on-rebuild`, so use CLI/source contract

## Milestone Checklist

- [ ] M0 complete
- [ ] M1 complete
- [ ] M2 complete
- [ ] M3 complete
- [ ] M4 complete
