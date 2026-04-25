# Assumptions

Updated: 2026-04-24

---

## A-001: obsidian-ops and obsidian-agent require no changes for v2

Both repos exist, work correctly, and already expose the right interface. The `/api/apply`,
`/api/undo`, `GET /api/health` contract in obsidian-agent is what forge-overlay proxies to and
what ops.js calls. No modifications needed.

If a bug is found during integration, it should be fixed in the respective repo and tagged before
forge v2 integration testing proceeds.

## A-002: ops.js / ops.css are the built output, static/src/ is the source

`static/ops.js` and `static/ops.css` are the browser-ready files served at `/ops/ops.js` and
`/ops/ops.css`. `static/src/` is the source. forge-overlay serves the `static/` directory.

If ops.js needs changes (e.g., to update the SSE event handling), the build step for `static/`
must be run before deploying forge-overlay. This process needs to be documented.

## A-003: kiln v0.9.5 is the fork baseline

If kiln releases a new version during Phase 1, evaluate whether to rebase the fork before tagging.
The diff is small enough that rebasing is low-risk.

## A-004: The /api/* contract is frozen for v2

`POST /api/apply`, `POST /api/undo`, `GET /api/health` request/response shapes do not change in
v2. ops.js, forge-overlay's proxy, and obsidian-agent all depend on them. Any future contract
change requires a versioned path (`/api/v2/apply`) and coordinated update across all three.

## A-005: Python 3.12+ for forge-overlay, 3.13+ for obsidian-agent

obsidian-agent already requires Python 3.13. forge-overlay targets 3.12+ (asyncio.TaskGroup,
tomllib). forge (orchestrator) should match forge-overlay at 3.12+.

## A-006: Tailscale remains the production networking layer

Docker Compose services run in `network_mode: service:tailscale`. forge-overlay binds on 0.0.0.0
(accessible via tailscale). obsidian-agent binds on 127.0.0.1 (internal only, accessed by
forge-overlay proxy). kiln-fork has no network binding.

## A-007: The old Go forge repo is archived, not deleted

After v2 is validated, rename `Bullish-Design/forge` to `forge-go-archive` and archive it on
GitHub. Do not delete — git history is valuable for reference.
