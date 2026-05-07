# Context

Updated: 2026-04-27

## Why This Project Exists

`forge-overlay` already owns the browser edge for Forge. The next gap is queue/job exposure: browser clients need a reliable way to submit async work, poll for progress, and receive status updates without forcing the overlay to become a queue engine.

The refactor exists because the current boundary is too thin for the new `obsidian-agent` job APIs. The overlay must understand enough about the upstream lifecycle to proxy it correctly, but not so much that it starts owning queue state.

## The Solution

Keep the architecture split clean:

| Component | Responsibility | Notes |
|---|---|---|
| `obsidian-agent` | Queue/job execution | Owns job creation, persistence, polling, and streaming semantics |
| `forge-overlay` | Transport and bridge layer | Proxies job endpoints, preserves browser semantics, maps transport failures |
| Browser clients | User interaction | Submit jobs, poll status, and reconnect to streams if needed |

## Key Facts

- The overlay should expose `/api/*` without embedding queue logic.
- Long-running operations must favor submit-and-poll or submit-and-stream flows.
- Transport failures need stable client-facing mapping.
- Streaming support should be optional and proxy-like, not queue-aware.
- Observability is part of the contract because debugging async jobs without correlation is slow.

## Project Boundaries

This project does not:
- Implement queue persistence
- Schedule jobs
- Retry or rebalance work
- Change the upstream job model in `obsidian-agent`

This project does:
- Define the proxy semantics for queue/job traffic
- Record the error and timeout policy
- Prepare the repo for implementation work in a later phase

## Document Map

| File | Purpose |
|---|---|
| `README.md` | Project scope and deliverables |
| `CONTEXT.md` | Why the project exists and the boundary it enforces |
| `DECISIONS.md` | Architecture and behavior decisions for the refactor |
| `DESIGN.md` | Concrete technical design for queue/proxy behavior |
| `IMPLEMENTATION.md` | Ordered implementation plan and milestones |
| `STATUS.md` | Current state, open questions, next action |
