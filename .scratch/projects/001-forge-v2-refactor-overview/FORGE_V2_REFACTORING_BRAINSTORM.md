# Forge v2 Refactoring Brainstorm

Updated: 2026-04-24

---

## Why This Refactor

The current forge codebase is a Go binary that has accumulated the wrong responsibilities:

- It forks kiln (a Go SSG) and adds overlay/proxy/SSE in Go
- It contains `internal/ops` — a deprecated, unreachable in-process LLM agent written in Go
- The team's primary language is Python; the LLM ecosystem is better in Python
- Two Python repos already exist (`obsidian-ops`, `obsidian-agent`) that do what `internal/ops`
  was trying to do, and they do it better

The refactor's goal is to align ownership with capability:
- **Go does what Go is good at:** fast, compiled SSG with a minimal diff from upstream kiln
- **Python does what Python is good at:** HTTP middleware, LLM orchestration, runtime iteration

---

## What Already Exists

The good news: most of the "new" work is already done.

### obsidian-ops (Bullish-Design/obsidian-ops)

A pure Python vault operations library. No LLM, no HTTP server.

- `Vault` class: file CRUD, frontmatter management, markdown patching, glob search
- JJ VCS: commit and undo
- Path traversal protection
- Python 3.12+, MIT license

This is the vault mechanics layer. obsidian-agent imports it. forge-overlay does not touch it.

### obsidian-agent (Bullish-Design/obsidian-agent)

A FastAPI HTTP service that wraps obsidian-ops with LLM orchestration.

- `POST /api/apply`, `POST /api/undo`, `GET /api/health`
- Uses pydantic-ai for LLM integration (supports Anthropic, OpenAI-compatible)
- Configured via env vars: `AGENT_VAULT_DIR`, `AGENT_LLM_MODEL`, etc.
- Python 3.13+

This is the agent layer. It already exposes exactly the `/api/*` contract that the overlay UI
calls. **No changes to obsidian-ops or obsidian-agent are required for v2.**

### static/ (in current forge repo)

The overlay UI already exists as a proper JavaScript project:

- `static/ops.js` + `static/ops.css` — built output (served to browsers)
- `static/src/` — source modules: SSE client, LLM instruction form, CodeMirror editor, state
  management, API client, page context
- Tests under `static/src/__tests__/`

This moves to forge-overlay and is served at `/ops/*`. **No changes to the JS needed.**

---

## What Needs to Be Built

### 1. kiln-fork (~25 lines of Go)

Fork kiln v0.9.5. Add two flags to `internal/cli/dev.go`:

```
--no-serve              skip server.Serve() call in dev/watch mode
--on-rebuild <url>      POST {"type":"rebuilt"} to this URL after each build
```

That is the entire Go work. File an upstream PR to kiln — if accepted, the fork eventually
dissolves. Until then, sync from upstream via `git fetch upstream` after each kiln release.
Conflicts will only ever be in `internal/cli/dev.go`.

### 2. forge-overlay (new Python package)

The only genuinely new component. A Starlette HTTP server that:

- Serves static files from kiln's output directory with clean URL resolution
- Injects ops.css + ops.js into HTML responses
- Brokers SSE at `/ops/events`
- Serves `/ops/*` from the `static/` directory
- Reverse-proxies `/api/*` to obsidian-agent
- Receives `/internal/rebuild` POST from kiln-fork → triggers SSE broadcast

**Technology:** Starlette + sse-starlette + httpx + Python 3.12+

**Key implementation note:** The injection middleware must buffer HTML responses to insert before
`</head>`. It must short-circuit for non-HTML content types (images, JSON, CSS, JS assets from
kiln's output) to avoid buffering static assets unnecessarily.

### 3. forge (Python rewrite of current Go CLI)

The current Go `forge` CLI becomes a Python package. Same commands, new implementation:

- Reads `forge.yaml`
- Translates config into subprocess invocations for each component
- Starts forge-overlay → obsidian-agent → kiln-fork in that order
- Monitors health and handles graceful shutdown
- Provides Docker Compose stack for production

**Technology:** Python 3.12+ + pydantic-settings + honcho (or custom subprocess manager)

---

## What Kiln Is (and Isn't)

From direct inspection of github.com/otaleghani/kiln v0.9.5:

- All packages are `internal/` — cannot be imported as a Go library. forge must remain a fork.
- The server is a pure static file server. No SSE, no injection, no proxy.
- The watcher has no HTTP notification mechanism (`OnRebuild` is a Go function, not a webhook).
- `kiln dev` = build + watch + HTTP server in one process. To remove the HTTP server, we need
  `--no-serve`.

The upstream PR for the two flags is worth filing. The changes are small and generically useful
(any project wanting to put a different server in front of kiln's build output would benefit).

---

## Architecture Decisions Summary

All major decisions are resolved. See DECISIONS.md for full rationale.

| Decision | Resolution |
|---|---|
| D-001: Static serving | forge-overlay owns it directly (no proxy to kiln) |
| D-002: Rebuild notification | kiln-fork --on-rebuild webhook |
| D-003: obsidian-agent deployment | Standalone server (unchanged) |
| D-004: forge role | Python CLI (local) + Docker Compose (production) |
| D-005: VCS backend | JJ via obsidian-ops (unchanged) |
| D-006: LLM providers | pydantic-ai via obsidian-agent (unchanged) |
| D-007: Upstream tracking | Manual sync + upstream PR |
| D-008: kiln-fork repo | Fresh fork from v0.9.5 |
| D-009: forge-overlay stack | Starlette + sse-starlette + httpx |
| D-010: Config model | forge.yaml + FORGE_* env vars |

---

## Risk Register

**R-1: Injection middleware correctness**
Buffering ASGI responses and modifying HTML is fiddly. Risk: injecting into wrong content types,
breaking Content-Length, double-injecting on cached responses.
Mitigation: unit tests covering HTML, JSON, image, CSS, chunked responses. Only inject when
Content-Type contains `text/html`.

**R-2: Startup race condition (first rebuild webhook)**
If kiln-fork starts and completes its first build before forge-overlay is listening, the first
webhook fires into the void. Browser never gets the initial SSE.
Mitigation: forge orchestrator waits for forge-overlay `/ops/events` to return 200 before
launching kiln-fork. This health gate is a few lines in the forge CLI startup sequence.

**R-3: kiln upstream divergence**
If kiln releases significant changes before the upstream PR is accepted, the fork diff can grow.
Mitigation: keep all forge-specific changes confined to `internal/cli/dev.go`. Periodic sync
reviews catch any conflicts early.

**R-4: obsidian-agent API contract drift**
If obsidian-agent changes its `/api/*` response schema, ops.js breaks silently (no type safety
at the proxy layer). Mitigation: document the contract explicitly, pin obsidian-agent version in
the Docker Compose stack and the forge orchestrator.

**R-5: ops.js / forge-overlay SSE event format**
ops.js expects `{"type":"rebuilt"}` as the SSE event data. kiln-fork must send exactly this.
If kiln-fork's webhook payload or forge-overlay's broadcast format diverges from what ops.js
expects, live reload silently stops working.
Mitigation: integration test that verifies the full chain end-to-end (vault edit → SSE received
with correct payload → reload).

---

## Opportunities

**Upstream PR to kiln:** The two flags (`--no-serve`, `--on-rebuild`) are genuinely useful beyond
this project. Any team running kiln behind a custom server (nginx, Caddy, another language's dev
server) would benefit. If accepted, kiln-fork eventually becomes zero-diff from upstream.

**obsidian-ops as a general Obsidian vault library:** obsidian-ops already has clean abstractions.
With forge v2 using it (indirectly via obsidian-agent), it becomes battle-tested for other
projects building on Obsidian vaults from Python.

**forge-overlay as a reusable pattern:** The overlay package (static serving + HTML injection +
SSE + proxy) is not Obsidian-specific. It could be useful for any project wanting to add an
interactive UI layer on top of a static site generator. Worth keeping the Obsidian-specific logic
(ops.js, the /api/* contract) separate from the generic HTTP machinery.

**pydantic-ai in obsidian-agent:** pydantic-ai handles multi-provider LLM support, tool schemas,
and structured outputs better than the raw HTTP implementation in the old Go `internal/ops`.
The switch is already made — this is a quality improvement inherited for free.
