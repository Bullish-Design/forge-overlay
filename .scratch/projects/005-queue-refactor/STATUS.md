# Status

Updated: 2026-04-27

## Executive Status

Queue refactor planning is defined, but implementation has not started.

## Investigation Summary

Confirmed from the concept doc:
- `forge-overlay` must stay transport-focused
- Queue/job logic belongs upstream in `obsidian-agent`
- The overlay needs robust proxy semantics for long-running jobs
- Optional streaming support should be treated as a pass-through concern

## Progress

- [x] Queue refactor concept captured
- [x] Project-scoped docs populated
- [ ] M0 Contract Capture complete
- [ ] M1 Proxy Behavior complete
- [ ] M2 Streaming Bridge complete
- [ ] M3 Error Mapping + Observability complete
- [ ] M4 Verification complete

## Open Issues

No implementation blockers yet. Remaining unknowns are the exact async job route names and whether upstream streaming will be SSE, websocket, or both.

## Next Action

Start M0 by verifying the current or planned `obsidian-agent` queue API contract and then lock the proxy behavior around that contract.
