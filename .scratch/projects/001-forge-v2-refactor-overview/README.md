# Project 17: Forge v2 Thin-Wrapper Refactor

Updated: 2026-04-24

## Objective

Replace the monolithic Go forge binary with five focused components.

## Components

| Component      | Language | Repo                           | Status   |
|----------------|----------|--------------------------------|----------|
| obsidian-ops   | Python   | Bullish-Design/obsidian-ops    | Existing — no changes needed |
| obsidian-agent | Python   | Bullish-Design/obsidian-agent  | Existing — no changes needed |
| kiln-fork      | Go       | Bullish-Design/kiln-fork       | New — fork of kiln + 2 flags |
| forge-overlay  | Python   | Bullish-Design/forge-overlay   | New — HTTP overlay server |
| forge          | Python   | Bullish-Design/forge           | Rewrite — Python CLI + Docker Compose |

## Current Status

Planning complete. All decisions resolved. Ready for M1 (kiln-fork).

## Where to Start

- **Understand the system:** ARCHITECTURE.md
- **Understand the decisions:** DECISIONS.md (all resolved)
- **Understand what to build:** EXECUTION_QUEUE.md (ordered implementation steps)
- **Track progress:** MILESTONE_CHECKLIST.md

## Key Insight

Most of "forge-llm" already exists. obsidian-ops handles vault mechanics; obsidian-agent handles
LLM orchestration via pydantic-ai. The ops.js overlay UI already lives in `static/`. The main
new work is forge-overlay (Python HTTP server) and the forge Python orchestrator. The Go work
is ~25 lines.
