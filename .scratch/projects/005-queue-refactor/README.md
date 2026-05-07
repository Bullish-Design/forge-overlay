# Project 005: Queue Refactor

Updated: 2026-04-27

## Objective

Refactor `forge-overlay` so async queue and job APIs from `obsidian-agent` are exposed reliably to browser clients without moving queue logic into the overlay.

## Scope

In scope:
- Preserve transport-only responsibility in `forge-overlay`
- Add proxy support for async queue/job endpoints under `/api/*`
- Support long-running job submission, status polling, and optional streaming bridges
- Tighten timeout, error mapping, and request/response observability

Out of scope:
- Queue persistence or scheduling in `forge-overlay`
- Job state mutation logic in `forge-overlay`
- Changes to `obsidian-agent` core queue semantics

## Minimal Project Docs

- `FORGE_OVERLAY_QUEUE_REFACTOR_CONCEPT.md`:
  High-level goals, responsibility boundary, and integration points
- `DESIGN.md`:
  Architecture, assumptions, and queue/proxy contract
- `IMPLEMENTATION.md`:
  Step-by-step execution plan and milestone checklist
- `STATUS.md`:
  Current status, open issues, and next action

## Deliverables

- Queue-aware proxy behavior for `obsidian-agent` APIs
- Optional streaming pass-through for job status updates
- Clear operational notes for timeouts, polling, and debugging
