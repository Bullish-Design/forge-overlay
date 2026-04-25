# Forge v2 Architecture

Updated: 2026-04-24

---

## Component Overview

| Component       | Language | Repo                              | Status   | Role |
|-----------------|----------|-----------------------------------|----------|------|
| kiln-fork       | Go       | Bullish-Design/kiln-fork (new)    | New      | SSG build + file watch |
| obsidian-ops    | Python   | Bullish-Design/obsidian-ops       | Existing | Vault operations library (no LLM) |
| obsidian-agent  | Python   | Bullish-Design/obsidian-agent     | Existing | LLM service, /api/* HTTP endpoints |
| forge-overlay   | Python   | Bullish-Design/forge-overlay (new)| New      | HTTP overlay: static serving, injection, SSE, proxy |
| forge           | Python   | Bullish-Design/forge              | Rewrite  | Python orchestrator CLI + Docker Compose |

---

## System Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  Browser                                                             │
│    GET /my-note    GET /ops/events    POST /api/apply                │
└──────┬──────────────────┬───────────────────┬────────────────────────┘
       │                  │                   │
┌──────▼──────────────────▼───────────────────▼────────────────────────┐
│  forge-overlay  (Python — Starlette — port 8080, public)             │
│                                                                      │
│  /*            static files from kiln output dir + clean URLs        │
│                + HTML injection (ops.css / ops.js before </head>)    │
│  /ops/events   SSE broker → fires {"type":"rebuilt"} on rebuild      │
│  /ops/*        overlay static assets (ops.css, ops.js, src/)         │
│  /api/*        reverse proxy ────────────────────────────────────┐   │
│  /internal/    rebuild webhook (from kiln-fork, internal only)   │   │
└──────────────────────────────────────────────────────────────────┼───┘
                                                                   │
                         ┌─────────────────────────────────────────▼───┐
                         │  obsidian-agent  (Python — FastAPI — :8081)  │
                         │                                              │
                         │  POST /api/apply   LLM agent run             │
                         │  POST /api/undo    VCS revert                │
                         │  GET  /api/health  liveness                  │
                         │                                              │
                         │  imports obsidian-ops for:                   │
                         │    Vault (file CRUD, frontmatter, search)    │
                         │    JJ VCS (commit, undo)                     │
                         │  uses pydantic-ai for LLM orchestration      │
                         └──────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  kiln-fork  (Go binary — background process, no HTTP)                │
│                                                                      │
│  kiln generate   one-shot SSG build → writes to output dir           │
│  kiln watch      build + watch + incremental rebuild (no HTTP)       │
│                  POST /internal/rebuild → forge-overlay on each done │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│  forge  (Python CLI + Docker Compose — user entry point)             │
│                                                                      │
│  forge dev       starts all three above, wires rebuild webhook       │
│  forge generate  runs kiln-fork generate once                        │
│  forge serve     starts forge-overlay only (no watcher)             │
│  forge init      scaffolds vault + forge.yaml                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## What Each Component Owns

### kiln-fork (Go)

A fork of https://github.com/otaleghani/kiln with exactly two additions:

1. `--no-serve` flag on `kiln dev` — runs build + watch without starting an HTTP server
2. `--on-rebuild <url>` flag — POSTs `{"type":"rebuilt"}` to a URL after each successful build

Everything else is upstream kiln: Obsidian vault parsing, Goldmark markdown rendering, theme/layout
system, incremental rebuild with dependency graph, clean URL static server (for `kiln serve` only).

**What it does not own:** HTTP serving in dev/watch mode, SSE, overlay injection, LLM, proxying.

---

### obsidian-ops (Python — existing)

A pure vault operations library. No HTTP server, no LLM.

Provides:
- `Vault` class: file CRUD, frontmatter management, markdown patching by heading/block reference
- Glob-based file listing and search
- JJ VCS integration: commit, undo
- Path traversal protection (sandboxed to vault root)

obsidian-agent imports this. forge-overlay does not import this directly.

---

### obsidian-agent (Python — existing)

A FastAPI HTTP service. Exposes the `/api/*` contract that forge-overlay proxies to.

Provides:
- `POST /api/apply` — takes an instruction + current URL path, runs LLM agent loop, returns summary
- `POST /api/undo` — reverts last VCS commit via obsidian-ops
- `GET /api/health` — liveness check

Uses pydantic-ai for LLM orchestration. Supports Anthropic and OpenAI-compatible providers.
Imports obsidian-ops for all vault and VCS operations.

**The `/api/*` contract is fixed.** forge-overlay, obsidian-agent, and the overlay UI JavaScript
(ops.js) all depend on it. Changes require coordinated updates.

---

### forge-overlay (Python — new)

A Starlette HTTP server. The browser's single entry point for everything.

Provides:
- Static file serving from kiln's output directory with clean URL resolution
- HTML injection middleware: inserts `<link ops.css>` and `<script ops.js>` before `</head>`
- SSE broker at `/ops/events`: broadcasts `{"type":"rebuilt"}` to connected browsers
- `/ops/*` static asset serving (ops.css, ops.js, src/ — from forge's `static/` directory)
- `/api/*` reverse proxy to obsidian-agent
- `/internal/rebuild` POST endpoint: receives kiln-fork webhook, triggers SSE broadcast

**What it does not own:** LLM logic, vault operations, site generation.

---

### forge (Python — rewrite from Go)

The user-facing orchestrator. Currently a Go binary; becomes a Python CLI.

Provides:
- Unified `forge.yaml` configuration (vault dir, output dir, ports, LLM provider, VCS backend)
- `forge dev`: starts kiln-fork (watch mode), forge-overlay, obsidian-agent in correct order
- `forge generate`: runs kiln-fork generate once
- `forge serve`: runs forge-overlay only (no watcher, static preview)
- `forge init`: scaffolds vault directory and forge.yaml
- Docker Compose stack for containerized deployment

Process startup order (important for webhook reliability):
1. forge-overlay (must be listening before kiln POSTs its first rebuild)
2. obsidian-agent
3. kiln-fork (starts building immediately; first webhook fires to already-listening overlay)

---

## Data Flows

### Normal page request

```
Browser GET /my-note
  → forge-overlay: look for /output/my-note.html
  → read file, detect text/html
  → injection middleware: insert ops.css + ops.js snippet before </head>
  → return modified HTML (200)
```

### Vault file edit → browser reload

```
User saves vault/my-note.md
  → kiln-fork fsnotify watcher fires
  → 300ms debounce elapses
  → kiln-fork incrementally rebuilds affected output files
  → kiln-fork POSTs {"type":"rebuilt"} to forge-overlay /internal/rebuild
  → forge-overlay SSE broker broadcasts {"type":"rebuilt"} to all connected browsers
  → ops.js receives event → location.reload()
  → browser requests new page → forge-overlay serves updated HTML
```

### LLM instruction

```
User submits instruction in overlay UI
  → ops.js POSTs {"instruction": "...", "current_url_path": "..."} to /api/apply
  → forge-overlay reverse-proxies to obsidian-agent /api/apply
  → obsidian-agent resolves current_url_path → vault file path
  → obsidian-agent acquires mutation lock
  → obsidian-agent runs pydantic-ai agent loop:
      LLM API call → tool calls → obsidian-ops Vault.write() → repeat until done
  → obsidian-ops commits changed files via JJ
  → obsidian-agent returns {"ok": true, "summary": "...", "changed_files": [...]}
  → forge-overlay proxies response back to ops.js
  → ops.js displays summary in overlay UI
  → meanwhile: kiln-fork detects changed vault files → rebuilds → webhook → SSE → reload
```

---

## What Happens to the Current Forge Go Repo

| Package              | Fate in v2                                              |
|----------------------|---------------------------------------------------------|
| `internal/builder`   | Becomes kiln-fork (carry forward as Go SSG core)        |
| `internal/obsidian`  | Becomes kiln-fork                                       |
| `internal/watch`     | Becomes kiln-fork (add `--no-serve` + `--on-rebuild`)   |
| `internal/server`    | Becomes kiln-fork (used only for `kiln serve`, not dev) |
| `internal/proxy`     | Deleted — moved to forge-overlay (Python httpx)         |
| `internal/overlay`   | Deleted — moved to forge-overlay (Python Starlette)     |
| `internal/ops`       | Deleted — superseded by obsidian-ops + obsidian-agent   |
| `internal/cli/dev.go`| Becomes kiln-fork (stripped of overlay/proxy wiring)    |
| `static/`            | Moves to forge-overlay (served at /ops/*)               |
| `docker/`            | Becomes forge Docker Compose stack (updated services)   |
| `cmd/forge/`         | Deleted — Python forge CLI takes over                   |
