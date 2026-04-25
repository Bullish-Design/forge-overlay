# Initial Investigation Status

Date: 2026-04-25  
Scope: Compare Project 17 plan artifacts with the current `forge` repository state.

## Executive Verdict

The library is **partially separated**, but **not yet separated according to the Project 17 v2 plan**.

What is already true:
- Runtime API ownership has been moved toward `obsidian-agent` (Forge now proxies `/api/*` in `dev`/Docker paths).
- `internal/ops` is explicitly marked deprecated for runtime use.
- Docker/demo flows already run a separate `obsidian-agent` process.

What is not yet true (major gaps):
- No `kiln-fork` repo with `--no-serve` and `--on-rebuild` flags.
- No standalone Python `forge-overlay` package (Starlette/httpx/sse-starlette).
- No Python `forge` orchestrator CLI (`forge.yaml`, process manager, health-gated startup).
- This repo is still a Go module/binary combining build/watch/serve plus Forge extensions.

## Evidence Reviewed

### Project 17 planning artifacts
- `.scratch/projects/17-v2-thin-wrapper-refactor/ARCHITECTURE.md`
- `.scratch/projects/17-v2-thin-wrapper-refactor/PLAN.md`
- `.scratch/projects/17-v2-thin-wrapper-refactor/EXECUTION_QUEUE.md`
- `.scratch/projects/17-v2-thin-wrapper-refactor/MILESTONE_CHECKLIST.md`
- `.scratch/projects/17-v2-thin-wrapper-refactor/PROGRESS.md`
- `.scratch/projects/17-v2-thin-wrapper-refactor/DECISIONS.md`

### Current repo artifacts
- `README.md`, `USER_GUIDE.md`, `docker/README.md`, `demo/README.md`
- `go.mod`, `cmd/forge/main.go`
- `internal/cli/dev.go`, `internal/cli/serve.go`, `internal/cli/generate.go`, `internal/config/config.go`
- `internal/server/mux.go`, `internal/server/server.go`
- `internal/overlay/*`, `internal/proxy/reverse.go`
- `internal/ops/*` and `internal/ops/README.md`
- `static/src/api.js`, `static/src/events.js`
- `docker/docker-compose.yml`, `docker/entrypoint.sh`, `docker/forge.Dockerfile`, `docker/agent.Dockerfile`
- `demo/run_demo.sh`, `forge_smoke/smoke_test.py`

### Validation run during investigation
- `go test ./...` (pass)
- `npm run test:ops` (pass)
- Full Docker/demo E2E not re-run in this investigation pass.

## Current State vs Target Architecture

| Target Component | Target per Plan | Current Reality in This Repo | Status |
|---|---|---|---|
| `kiln-fork` (Go) | Separate fork of upstream Kiln v0.9.5 with only `--no-serve` + `--on-rebuild` additions | This repo itself is a Go fork-like codebase with Forge-specific flags (`--proxy-backend`, `--overlay-dir`, `--inject-overlay`), no `--no-serve`, no `--on-rebuild` webhook path | Not started vs plan |
| `forge-overlay` (Python) | New Starlette service for static serving, injection, SSE, proxy | Equivalent behavior exists but in Go (`internal/server`, `internal/overlay`, `internal/proxy`) | Not started vs plan |
| `forge` orchestrator (Python) | Thin process orchestrator CLI (`forge dev/generate/serve/init`) managing kiln+overlay+agent | Current `forge` is still Go, directly owns build/watch/serve runtime behavior | Not started vs plan |
| `obsidian-agent` | Separate service handling LLM + `/api/*` | Used externally in Docker/demo (`obsidian-agent:local`, separate process) | Partially aligned |
| `obsidian-ops` | Separate library imported by obsidian-agent | Used externally via obsidian-agent image build; not in this repo | Partially aligned |

## Separation Assessment

### 1) Runtime/API separation

Current:
- `forge dev` routes `/api/*` through proxy when `--proxy-backend` is provided.
- In `internal/cli/dev.go`, `APIHandler` is explicitly nil; proxy is used through `ForgeConfig`.
- `internal/ops/README.md` states `internal/ops` is no longer wired into runtime API handling.

Implication:
- This is a meaningful step toward separation, but only at runtime behavior level.
- Code ownership/repo boundaries are not yet split the way Project 17 defines.

### 2) Build/watch/serve separation

Current:
- `forge dev` (Go) still performs initial build, in-process file watching, incremental rebuild, SSE publication, and HTTP serving in one binary.
- Rebuild notification is in-process (`eventBroker.Publish`) rather than webhook from kiln to overlay.

Target:
- `kiln-fork` owns build/watch and posts webhook.
- `forge-overlay` owns HTTP/static/injection/SSE/proxy.

Gap:
- Core control flow is still coupled in one process.

### 3) Configuration model

Current:
- Config file is `kiln.yaml` (`internal/config/config.go`).
- Docker uses env vars and entrypoint wiring to run `forge dev`.

Target:
- Unified `forge.yaml` + `FORGE_*` overrides for orchestrator-driven component wiring.

Gap:
- Config schema/orchestration layer from plan does not exist yet.

### 4) API contract alignment risk

Project 17 assumes a stable `/api/apply`, `/api/undo`, `/api/health` contract.  
Current `static/src/api.js` calls expanded paths (`/api/agent/apply`, `/api/vault/*`, `/api/vault/undo`) in addition to `/api/undo`.

Implication:
- Before implementation, confirm the real obsidian-agent contract to avoid building v2 around stale assumptions.
- This is a critical pre-M1/pre-M2 clarification item.

## Milestone Status Against Project 17

### M1 (`kiln-fork`)
- Not done.
- No separate `Bullish-Design/kiln-fork` implementation in this workspace.
- Required flags and webhook behavior are not present in current Forge CLI.

### M2 (`forge-overlay`)
- Not done as a Python package.
- Functionality exists in Go and can be ported, but code ownership/repo boundary is not yet implemented.

### M3 (Python `forge` orchestrator)
- Not done.
- No Python package for orchestration exists; current `pyproject.toml` is only for smoke tooling (`forge-smoke`).

### M4 (full v2 integration validation)
- Not done relative to v2 architecture.
- Existing tests validate current Go-based architecture, not the planned v2 componentized architecture.

## What Needs To Be Done Next

## Phase 0.5: Contract/Scope Lock (must happen first)
- Confirm canonical obsidian-agent API endpoints and payloads actually used by current overlay UI.
- Update Project 17 assumptions/docs to match reality (or intentionally migrate UI contract).
- Decide whether to preserve endpoint aliases (`/api/apply` vs `/api/agent/apply`) during migration window.

## M1: Build `kiln-fork`
- Create fresh fork from upstream Kiln v0.9.5.
- Add only:
  - `--no-serve`
  - `--on-rebuild <url>` with non-fatal POST-on-success rebuild hook.
- Keep diff minimal and test suite green.
- Tag and upstream PR.

## M2: Build Python `forge-overlay`
- Port current Go behavior to Starlette:
  - Clean URL static serving + custom 404
  - HTML injection (`/ops/ops.css`, `/ops/ops.js`)
  - SSE broker at `/ops/events`
  - `/internal/rebuild` webhook endpoint
  - `/api/*` reverse proxy to obsidian-agent
- Keep overlay JS/CSS as static assets served at `/ops/*`.

## M3: Rewrite `forge` as Python orchestrator
- Introduce `forge.yaml` schema + env overrides.
- Implement process manager with startup ordering:
  1. `forge-overlay`
  2. `obsidian-agent`
  3. `kiln-fork` (watch mode + rebuild webhook)
- Implement `dev`, `generate`, `serve`, `init`.
- Migrate Docker compose to distinct services (`kiln-fork`, `forge-overlay`, `obsidian-agent`, `tailscale`).

## M4: Validate and cut over
- Run full end-to-end checks for:
  - file edit rebuild/reload
  - instruction/apply flow
  - undo flow
  - docker stack behavior
- Verify kiln-fork diff size and archive old Go repo path per plan.

## Key Risks to Manage

- API contract drift between overlay UI and obsidian-agent.
- Hidden coupling in current Go code paths when porting behavior to Python.
- Startup race conditions for first rebuild event (already addressed in plan by health gating).
- Transition period where both old (`/api/apply`) and new (`/api/agent/apply`) endpoints may be required.

## Conclusion

Project 17 planning is solid, but implementation is still at **pre-M1** relative to the intended v2 structure.  
The current repo represents an intermediate architecture: Go-based Forge with proxy-first runtime and external obsidian-agent integration, not the final thin-wrapper split.
