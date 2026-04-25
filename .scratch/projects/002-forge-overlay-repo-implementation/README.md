# Project 002: forge-overlay Repository Implementation

Updated: 2026-04-25

## Objective

Turn this repository from a Python template into the standalone `forge-overlay` service.

## Scope

In scope:
- Build and test the `forge_overlay` package
- Implement static serving, HTML injection, SSE, and `/api/*` proxy behavior
- Add configuration and runtime entrypoint for this repo

Out of scope:
- Implementing `kiln-fork`
- Implementing the Python `forge` orchestrator
- Modifying `obsidian-agent`

## Minimal Project Docs

- `DESIGN.md`:
  Context, architecture, assumptions, and decisions
- `IMPLEMENTATION.md`:
  Phase plan, execution order, and milestone checklist
- `STATUS.md`:
  Current status, investigation summary, open issues, and next action

## Deliverables

- `src/forge_overlay/` implementation
- `tests/` coverage for core behaviors
- `pyproject.toml` aligned to the package and dependencies
