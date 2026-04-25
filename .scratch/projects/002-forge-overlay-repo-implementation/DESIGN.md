# Design

Updated: 2026-04-25

## Context

`forge-overlay` is the browser-facing HTTP edge service for Forge v2. This repo is currently a template and does not yet implement the service.

Required responsibilities:
- Serve generated site output with clean URL behavior
- Inject overlay assets into HTML responses
- Expose SSE for rebuild notifications
- Proxy `/api/*` to `obsidian-agent`
- Accept rebuild webhooks from `kiln-fork`

External contracts:
- `kiln-fork` sends rebuild notifications to `POST /internal/rebuild`
- `obsidian-agent` serves stable `/api/*` endpoints
- Overlay assets (`ops.js`, `ops.css`) exist in a configured static directory

## Kiln-Fork Contract (Verified)

Source inspected: `internal/cli/dev.go`, `internal/cli/commands.go`, `internal/server/server.go`, and demo smoke logs in `demo/logs/`.

1. Forge integration command is `kiln dev`, not `kiln watch`.
2. Required flags are `--no-serve` and `--on-rebuild <url>`.
3. Webhook payload is exactly `{"type":"rebuilt"}` with `Content-Type: application/json`.
4. Webhook POST timeout is 5 seconds and failures are logged but non-fatal.
5. `--no-serve` still performs initial build, sets up watcher, and blocks until signal.
6. Webhook is emitted from the incremental rebuild callback, not the initial full build.
7. Existing kiln docs (`docs/Commands/dev.md`) have not been updated for these two new flags, so overlay planning should follow CLI code behavior.

## Architecture

Route ownership:
- `POST /internal/rebuild`: broadcast `{"type":"rebuilt"}`
- `GET /ops/events`: SSE stream
- `GET /ops/{path:path}`: overlay static assets
- `ANY /api/{path:path}`: reverse proxy to `obsidian-agent`
- `GET /{path:path}`: static output serving + HTML injection

Module layout:
- `src/forge_overlay/config.py`
- `src/forge_overlay/static_handler.py`
- `src/forge_overlay/inject.py`
- `src/forge_overlay/events.py`
- `src/forge_overlay/proxy.py`
- `src/forge_overlay/app.py`
- `src/forge_overlay/main.py`

## Decisions

1. Use Starlette + uvicorn runtime.
2. Use `src/forge_overlay` package with `create_app(config)` app factory.
3. Static resolution order:
   1. exact file
   2. `<path>.html`
   3. `<path>/index.html`
   4. `404.html` fallback (if present)
4. Match kiln dev-server trailing-slash canonicalization (`/foo/` -> `/foo`) for clean URL parity.
5. Inject snippet only for HTML responses containing `</head>`.
6. Rebuild event payload remains `{"type":"rebuilt"}` end-to-end.
7. `/internal/rebuild` should return quickly (204 preferred) and treat webhook input as a trigger, not a schema-heavy API.
8. Proxy forwards method, path, query, headers, body; returns upstream status, headers, body.
9. Keep Python baseline aligned to repo (`>=3.13`) unless intentionally changed.

## Assumptions

1. `/api/*` contract in `obsidian-agent` remains stable.
2. Rebuild signaling is webhook-driven (no overlay filesystem watcher).
3. `kiln-fork` initial full build does not emit a webhook event; rebuild events come after file-change rebuilds.
4. Overlay static bundle is available at runtime.
5. Repo starts from template state and needs full package/test scaffolding.
