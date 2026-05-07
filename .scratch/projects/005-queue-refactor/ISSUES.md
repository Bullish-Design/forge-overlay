# Issues

Updated: 2026-04-27

No open blockers. The current unknowns are contract details rather than implementation failures.

---

## Resolved Issues (for reference)

**QF-001 — Queue boundary definition** ✓ RESOLVED  
`forge-overlay` is transport-only. Queue persistence, scheduling, and state mutation stay in `obsidian-agent`.

**QF-002 — Browser-facing job lifecycle** ✓ RESOLVED  
Default behavior should be submit fast, then poll or stream for progress.

**QF-003 — Streaming support mode** ✓ RESOLVED  
Optional pass-through support for SSE or websocket-style upstream status streams.

**QF-004 — Error mapping policy** ✓ RESOLVED  
Transport failures map to stable overlay errors such as `upstream_timeout` and `upstream_unavailable`.

**QF-005 — Observability scope** ✓ RESOLVED  
Log correlation hints, job identifiers, upstream status, and duration without exposing sensitive payloads.

---

## Issue Log Format

When a new blocker appears during implementation:

```md
## ISSUE-NNN — Short title  [OPEN/RESOLVED]

Impact: What is blocked.
Root cause: What is causing the problem.
Options: Possible resolutions with tradeoffs.
Decision: What was decided (when resolved).
```
