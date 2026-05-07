# FORGE_OVERLAY_QUEUE_REFACTOR_CONCEPT

## Purpose
Define the overlay changes needed so async queue/job APIs from `obsidian-agent` are reliably exposed to browser clients.

## Responsibility Boundary
- `forge-overlay` is transport, injection, and event bridge.
- It should not implement core queue business logic.
- It should provide robust proxy semantics (timeouts/streaming/error mapping) for long-running jobs.

## What Needs To Change
1. Proxy support for async job endpoints
- Ensure `/api/*` pass-through supports new queue/job endpoints from agent.
- Validate support for long-running status polling and optional streaming endpoints.

2. Timeout and connection semantics
- Keep configurable proxy timeout for long operations.
- Ensure non-blocking patterns are preferred (submit -> immediate response with `job_id`; status via poll/stream).
- Improve error mapping consistency (`upstream_timeout`, `upstream_unavailable`, upstream status passthrough).

3. Optional streaming bridge
- If agent provides SSE/websocket status stream, ensure overlay can proxy it cleanly.
- Keep reconnect-friendly semantics for browser clients.

4. Observability
- Log request correlation hints (`job_id`, upstream status, durations) where possible.
- Preserve headers/body details needed for debugging without overexposing sensitive payloads.

## Non-Goals
- Queue persistence or mutation arbitration in overlay.
- Job scheduling logic in overlay.

## Integration Points
- Must mirror `obsidian-agent` API contract for job lifecycle endpoints.
- Consumed by `forge` production UI and demo scripts.
