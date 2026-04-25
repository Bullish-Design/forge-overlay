# Plan

Updated: 2026-04-24

## Objective

Build the Forge v2 system from five components — two existing, three new/rewritten:

| Component      | Work required |
|----------------|---------------|
| obsidian-ops   | None — already built and correct |
| obsidian-agent | None — already built and correct |
| kiln-fork      | New: fork kiln + add 2 flags (~25 lines Go) |
| forge-overlay  | New: Python HTTP overlay server |
| forge          | Rewrite: Python orchestrator CLI (currently a Go binary) |

## Principles

1. Do not change obsidian-ops or obsidian-agent unless a bug requires it.
2. Keep the kiln-fork diff from upstream as small as possible.
3. forge-overlay has no LLM awareness — it is pure HTTP infrastructure.
4. forge (the orchestrator) has no business logic — it only wires components together.
5. Each component is independently runnable and testable before integration.

## Phases

### Phase 0 — All decisions resolved ✓
All decisions documented in DECISIONS.md. No open blockers.

### Phase 1 — kiln-fork

Goal: A Go binary that builds and watches an Obsidian vault, posts a webhook on rebuild, and does
not start an HTTP server in watch mode.

Steps:
1. Fork `github.com/otaleghani/kiln` at v0.9.5 into `Bullish-Design/kiln-fork`
2. Add `--no-serve` flag to `internal/cli/dev.go`: skip `server.Serve(...)` call
3. Add `--on-rebuild <url>` flag: after each successful rebuild, POST `{"type":"rebuilt"}` to URL
4. Verify: `kiln watch --no-serve --on-rebuild http://localhost:9999/test` fires on vault change
5. Existing kiln test suite passes
6. Tag `v0.9.5-forge.1`
7. File upstream PR to `otaleghani/kiln`

### Phase 2 — forge-overlay

Goal: A Python HTTP server that serves kiln's output with overlay injection and SSE.

Steps:
1. Scaffold: `uv init forge-overlay`, deps: starlette, sse-starlette, httpx, uvicorn
2. Static file handler: serve from output dir with clean URL logic + 404 fallback
3. Injection middleware: buffer HTML responses, insert snippet before `</head>`
4. SSE broker: asyncio-based, broadcast to all connected clients
5. `/ops/events` endpoint wired to SSE broker
6. `/ops/*` StaticFiles mount (serves `static/` directory)
7. `/api/*` httpx reverse proxy to obsidian-agent
8. `/internal/rebuild` POST endpoint: triggers SSE broker broadcast
9. App factory function accepting config (output_dir, static_dir, agent_url, port)
10. Unit tests: injection middleware, SSE broker, proxy, static serving, 404 handling
11. Integration test with kiln-fork: edit vault file, verify SSE message received by client

### Phase 3 — forge (Python orchestrator)

Goal: A Python CLI that starts and manages all components, reads a unified config.

Steps:
1. Scaffold: `uv init forge`, deps: pydantic-settings, click (or typer), honcho (or asyncio)
2. `forge.yaml` config schema (pydantic model): vault_dir, output_dir, overlay_dir, ports,
   agent env vars, kiln flags
3. Process manager: start forge-overlay → obsidian-agent → kiln-fork in sequence
4. Health gate: wait for forge-overlay `/ops/events` 200 before starting kiln-fork
5. `forge dev` command
6. `forge generate` command (kiln-fork generate mode, no overlay or agent)
7. `forge serve` command (forge-overlay only, no watcher)
8. `forge init` command (scaffold vault + forge.yaml with defaults)
9. Graceful shutdown: SIGTERM to all child processes on Ctrl-C
10. Update Docker Compose stack: kiln-fork + forge-overlay + obsidian-agent + tailscale
11. Smoke test: `forge dev` from cold start, site loads in browser with overlay injected

### Phase 4 — Integration and validation

1. Full end-to-end: `forge dev`, edit vault file, browser reloads with updated content
2. Full end-to-end: submit LLM instruction via overlay UI, vault changes, browser reloads
3. Full end-to-end: `/api/undo`, vault reverts, browser reloads
4. Docker Compose full stack test
5. Verify kiln-fork diff from upstream is ≤50 lines
6. Archive the old Go forge repo

## Acceptance Criteria

- `forge dev` starts all components; site loads with ops.css/ops.js injected
- Editing a vault file triggers SSE and browser reload within ~1 second
- LLM instruction via overlay UI results in vault change and live reload
- `forge generate` produces identical output to running kiln directly
- kiln-fork diff from upstream kiln ≤50 lines
- obsidian-ops and obsidian-agent are unmodified from their current versions
