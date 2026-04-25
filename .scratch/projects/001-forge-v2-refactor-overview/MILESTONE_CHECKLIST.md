# Milestone Checklist

Updated: 2026-04-24

---

## M0 — Decisions and Prerequisites ✓ COMPLETE

- [x] All decisions resolved (see DECISIONS.md — all 10 resolved)
- [x] obsidian-ops confirmed as existing, no changes needed
- [x] obsidian-agent confirmed as existing, no changes needed
- [x] ops.js/ops.css confirmed in `static/` directory, no extraction needed
- [x] kiln-fork repo strategy: fresh fork from v0.9.5
- [x] forge-overlay tech stack: Starlette + sse-starlette + httpx

## M1 — kiln-fork

- [ ] kiln v0.9.5 forked into `Bullish-Design/kiln-fork`
- [ ] `--no-serve` flag added to `internal/cli/dev.go`
- [ ] `--on-rebuild <url>` flag added, fires POST after each successful rebuild
- [ ] Smoke test: `kiln watch --no-serve --on-rebuild http://localhost:9999/echo` fires on change
- [ ] Existing kiln test suite passes unchanged
- [ ] Tagged `v0.9.5-forge.1`
- [ ] Upstream PR filed to `otaleghani/kiln`

## M2 — forge-overlay

- [ ] Python package scaffolded (`forge_overlay/`)
- [ ] Static file serving with clean URL logic (no-extension → .html, dir → index.html, 404)
- [ ] Injection middleware (inserts snippet only into text/html responses)
- [ ] SSE broker (asyncio, broadcast to all connected clients, handles disconnects)
- [ ] `/ops/events` endpoint
- [ ] `/ops/*` StaticFiles mount serving `static/` directory
- [ ] `/api/*` httpx reverse proxy (configurable target URL, timeout)
- [ ] `/internal/rebuild` POST endpoint (triggers SSE broadcast)
- [ ] App factory function (config: output_dir, static_dir, agent_url, port)
- [ ] Unit tests: all middleware and handlers
- [ ] Integration test: kiln-fork → webhook → forge-overlay → SSE received by test client

## M3 — forge (Python orchestrator)

- [ ] Python package scaffolded (`forge_cli/`)
- [ ] `forge.yaml` pydantic config model
- [ ] `FORGE_*` env var overrides on all config fields
- [ ] Process manager: sequential startup with health gate
- [ ] `forge dev` command (all three components)
- [ ] `forge generate` command (kiln-fork only)
- [ ] `forge serve` command (forge-overlay only)
- [ ] `forge init` command (scaffold vault + forge.yaml)
- [ ] Graceful shutdown on SIGINT/SIGTERM
- [ ] Docker Compose updated: kiln-fork + forge-overlay + obsidian-agent + tailscale
- [ ] Smoke test: `forge dev` cold start → site loads in browser with overlay injected

## M4 — End-to-End Validation

- [ ] Vault edit → SSE fires → browser reloads with updated content (<1 second)
- [ ] Overlay UI instruction → obsidian-agent LLM run → vault change → rebuild → reload
- [ ] `/api/undo` → vault reverts → rebuild → reload
- [ ] Docker Compose full stack test (tailscale + all services)
- [ ] kiln-fork diff from upstream kiln ≤50 lines confirmed
- [ ] obsidian-ops and obsidian-agent repos unmodified
- [ ] Old Go forge repo archived
