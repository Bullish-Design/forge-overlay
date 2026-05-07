# Implementation

Updated: 2026-04-27

## Objective

Implement queue-aware proxying in `forge-overlay` without moving queue logic into the overlay itself.

## Phased Plan

### M0 Contract Capture

1. Identify the queue/job endpoints that `obsidian-agent` already exposes or will expose.
2. Record expected request/response shapes for:
   - job submission
   - job status polling
   - job result retrieval
   - optional status streaming
3. Capture timeout expectations and retry boundaries.
4. Document the error mapping policy for browser clients.

### M1 Proxy Behavior

1. Extend `/api/*` proxy handling for async job endpoints.
2. Preserve method, path, query string, request body, and required headers.
3. Strip hop-by-hop headers where appropriate.
4. Keep upstream status codes and headers intact when they are still meaningful.
5. Add configurable timeout handling for long-running operations.

### M2 Streaming Bridge

1. Detect whether the upstream exposes SSE or websocket status updates.
2. Proxy stream responses without unnecessary buffering.
3. Ensure browser reconnect semantics remain stable.
4. Validate that disconnected clients do not leak resources.

### M3 Error Mapping + Observability

1. Normalize upstream connection failures to `upstream_unavailable`.
2. Normalize upstream timeout cases to `upstream_timeout`.
3. Preserve upstream application errors when they convey actionable job state.
4. Add structured logging for:
   - correlation id
   - `job_id`
   - upstream route
   - upstream status
   - duration

### M4 Verification

1. Add direct tests for job submission proxying.
2. Add direct tests for polling/status endpoints.
3. Add tests for upstream timeout and connection failure mapping.
4. Add tests for optional streaming pass-through when supported.
5. Run the full test suite and fix any gaps.

## Milestone Checklist

- [ ] M0 contract capture complete
- [ ] M1 proxy behavior complete
- [ ] M2 streaming bridge complete
- [ ] M3 error mapping and observability complete
- [ ] M4 verification complete
