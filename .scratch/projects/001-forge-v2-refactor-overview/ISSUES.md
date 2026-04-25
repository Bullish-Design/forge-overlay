# Issues

Updated: 2026-04-24

No open blockers. All decisions resolved.

---

## Resolved Issues (for reference)

**OQ-001 — obsidian-agent relationship** ✓ RESOLVED
obsidian-ops is the vault library (no LLM). obsidian-agent is the LLM service (imports
obsidian-ops). Both already exist and require no changes for v2.

**OQ-002 — ops.js location** ✓ RESOLVED
Lives in `static/` in the current forge repo. `static/ops.js` and `static/ops.css` are built
output; `static/src/` is the source. forge-overlay serves this directory at `/ops/*`.
No extraction needed — it moves as-is to the forge-overlay repo.

**OQ-003 — D-001 static serving approach** ✓ RESOLVED
Option A: forge-overlay owns static file serving directly from kiln's output dir.

**OQ-004 — kiln-fork repo strategy** ✓ RESOLVED
Fresh fork from kiln v0.9.5.

---

## Issue Log Format

When a new blocker appears during implementation:

```
## ISSUE-NNN — Short title  [OPEN/RESOLVED]

Impact: What is blocked.
Root cause: What is causing the problem.
Options: Possible resolutions with tradeoffs.
Decision: What was decided (when resolved).
```
