# Decisions

Updated: 2026-04-24

---

## D-001 — How forge-overlay serves static content  [RESOLVED]

**Decision: Option A — forge-overlay owns static file serving directly.**

forge-overlay serves files directly from kiln's output directory and reimplements kiln's clean URL
logic in Python (~30 lines). kiln-fork always runs with `--no-serve`.

**Rationale:**
- Single HTTP hop for every page request (no proxy to kiln's server)
- forge-overlay already buffers HTML responses for injection — direct file access fits naturally
- Clean URL logic is small and stable; kiln has not changed it in recent releases
- Eliminates a second port and process from the network topology

**Rejected: Option B (proxy through kiln HTTP server)**
The double-hop adds complexity and latency. kiln's HTTP server stays unused in dev mode under
Option A, so there is no benefit to keeping it running.

---

## D-002 — Rebuild notification mechanism  [RESOLVED]

**Decision: Option A — kiln-fork `--on-rebuild` webhook.**

After each successful build, kiln-fork POSTs `{"type":"rebuilt"}` to `forge-overlay`'s
`/internal/rebuild` endpoint. forge-overlay's SSE broker then broadcasts to connected browsers.

**Rationale:**
- Explicit, reliable, zero timing ambiguity — SSE fires exactly once per completed rebuild
- No redundant file watcher (kiln already watches input; forge-overlay need not watch output)
- Causal chain is readable: build done → signal → SSE → reload

**Startup race mitigation:** forge orchestrator starts forge-overlay first and waits for it to be
healthy before starting kiln-fork. First rebuild webhook is guaranteed to find a listener.

**Rejected: Option B (forge-overlay watches output dir)**
Redundant watcher, timing ambiguity (SSE may fire before kiln finishes writing all output files),
harder to reason about.

---

## D-003 — obsidian-agent deployment: standalone server vs in-process  [RESOLVED]

**Decision: Option A — obsidian-agent runs as a standalone server (separate process).**

obsidian-agent already exists as a standalone FastAPI service. This model is kept as-is.
forge-overlay proxies `/api/*` to it via httpx.

**Rationale:**
- obsidian-agent already works this way — no change needed
- Process isolation: obsidian-agent doing blocking LLM calls (30–120s) cannot affect
  forge-overlay's SSE and static serving responsiveness
- obsidian-agent can be restarted, replaced, or run on a different machine independently
- Matches existing Docker Compose pattern

---

## D-004 — forge role: Python orchestrator + Docker Compose  [RESOLVED]

**Decision: Option C — Python CLI for local dev + Docker Compose for production.**

**Local dev:** `forge dev` is a Python CLI command that starts kiln-fork, forge-overlay, and
obsidian-agent as managed subprocesses in the correct order.

**Production:** Docker Compose stack with one container per component.

**Rationale:**
- Local dev must not require Docker (significant friction for daily iteration)
- Docker Compose handles production reliability (restarts, logging, healthchecks)
- Both modes use identical components and configuration, just different process managers

**Implementation:** Python `subprocess` + a Procfile-style manager (honcho or similar) for local
dev. The forge Python package is pip-installable.

---

## D-005 — VCS backend  [RESOLVED]

**Decision: JJ, as already implemented in obsidian-ops.**

obsidian-ops already implements JJ commit/undo via subprocess. This is the current behavior and
it works. No change needed.

**Future consideration:** obsidian-ops could add a git backend behind an abstraction. This is
out of scope for v2 but the obsidian-ops `Vault` class is the right place to add it if needed.

---

## D-006 — LLM provider support  [RESOLVED]

**Decision: Delegate entirely to obsidian-agent / pydantic-ai.**

obsidian-agent already handles provider selection via pydantic-ai, which supports Anthropic,
OpenAI-compatible endpoints, and others. forge-overlay and forge have no LLM awareness. No
decision needed at the forge level — configure obsidian-agent's env vars (`AGENT_LLM_MODEL`,
`AGENT_LLM_BASE_URL`, `ANTHROPIC_API_KEY`, etc.).

---

## D-007 — kiln-fork upstream tracking  [RESOLVED]

**Decision: Manual tracking with a documented diff, upstream PR filed.**

kiln releases on a slow cadence (~monthly). The fork diff touches only `internal/cli/dev.go`
(two flags). Merge strategy:

1. `git remote add upstream https://github.com/otaleghani/kiln`
2. After each kiln release, `git fetch upstream` and review the diff
3. Cherry-pick or merge non-conflicting changes
4. Conflicts expected only in `internal/cli/dev.go`

File a PR to upstream kiln for `--no-serve` and `--on-rebuild`. If accepted, kiln-fork
eventually dissolves back into a direct dependency.

---

## D-008 — kiln-fork repo strategy  [RESOLVED]

**Decision: Fresh fork from kiln v0.9.5.**

The existing `Bullish-Design/forge` Go repo has 18+ months of mixed history. A fresh fork gives:
- A clean, auditable diff from upstream (two commits: "fork kiln v0.9.5" + "add flags")
- Clear communication to readers: "this is kiln plus these two things"

The existing forge Go repo is archived after kiln-fork is validated.

---

## D-009 — forge-overlay technology stack  [RESOLVED]

**Decision: Starlette (not FastAPI) + sse-starlette + httpx.**

- **Starlette** over FastAPI: forge-overlay has no need for OpenAPI schema generation. It is
  middleware-heavy (injection, SSE, proxy) and Starlette's lower-level ASGI API fits better.
- **sse-starlette**: well-maintained SSE library, handles client disconnection correctly.
- **httpx**: async HTTP client for the `/api/*` proxy, consistent with the rest of the Python stack.

obsidian-agent uses FastAPI (appropriate there — it has structured request/response schemas).

---

## D-010 — forge configuration model  [RESOLVED]

**Decision: `forge.yaml` + `FORGE_*` environment variable overrides.**

Single config file at the project root covers all components:

```yaml
vault_dir: ./vault
output_dir: ./public
overlay_dir: ./static   # ops.css, ops.js, src/ — served at /ops/*
port: 8080

agent:
  port: 8081
  vault_dir: ./vault    # passed to obsidian-agent via env
  llm_model: claude-sonnet-4-6
  # api_key from ANTHROPIC_API_KEY env var

vcs:
  backend: jj           # obsidian-ops handles this

kiln:
  input_dir: ./vault
  output_dir: ./public
  theme: default
  # ... other kiln flags
```

forge reads this file, derives the correct flags for each subprocess, and launches them.
obsidian-agent and kiln-fork use their own env var / flag conventions; forge translates.
