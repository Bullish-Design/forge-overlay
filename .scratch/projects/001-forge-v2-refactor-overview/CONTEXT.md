# Context

Updated: 2026-04-24

## Why This Project Exists

The current `Bullish-Design/forge` is a Go binary — a fork of the kiln Obsidian SSG — with a
large amount of Go code that the team doesn't want to own: in-process LLM agent, overlay HTTP
middleware, SSE broker, reverse proxy. Two Python repos (`obsidian-ops`, `obsidian-agent`) already
do the LLM/vault work better. The Go code is the wrong layer in the wrong language.

## The Solution

Replace the monolithic Go forge with five components that each own exactly one thing:

| Component      | Language | Status   | What it does |
|----------------|----------|----------|--------------|
| obsidian-ops   | Python   | Existing | Vault file ops + VCS library |
| obsidian-agent | Python   | Existing | LLM service, /api/* HTTP endpoints |
| kiln-fork      | Go       | New      | SSG build + watch (2 flag additions to kiln) |
| forge-overlay  | Python   | New      | HTTP overlay: static, injection, SSE, proxy |
| forge          | Python   | Rewrite  | Orchestrator CLI + Docker Compose |

## Key Facts

- obsidian-ops and obsidian-agent require no changes
- ops.js / ops.css already live in `static/` — no extraction needed
- kiln-fork diff from upstream kiln is ~25 lines (two flags)
- forge-overlay is the only genuinely new component
- forge becomes Python (currently Go)

## Prior Work

- Project 16 (`16-forge-library-deep-dive`): Full analysis of the current Go forge codebase
- Project 17 (this): Architecture design and build plan for v2

## Document Map

| File | Purpose |
|------|---------|
| ARCHITECTURE.md | Component diagram, data flows, interface definitions |
| DECISIONS.md | 10 decisions — all resolved with rationale |
| FORGE_V2_REFACTORING_BRAINSTORM.md | Narrative: why, what exists, what's new, risks, opportunities |
| PLAN.md | Phased build plan with acceptance criteria |
| MILESTONE_CHECKLIST.md | Per-milestone granular checklist |
| EXECUTION_QUEUE.md | Ordered implementation steps, ready to execute |
| PROGRESS.md | Current status |
| ISSUES.md | Resolved issue log |
| ASSUMPTIONS.md | Recorded assumptions |
| CONTEXT.md | This file |
