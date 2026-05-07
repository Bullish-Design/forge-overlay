# Execution Queue

Updated: 2026-04-27

All decisions are resolved at the planning level. Work items are ordered for implementation.

---

## M1 — Contract capture

1. Confirm the exact queue/job endpoint surface in `obsidian-agent`.
2. Record request and response shapes for:
   - job submission
   - status polling
   - result retrieval
   - optional event streaming
3. Document the expected timeout and retry boundary for each route.
4. Freeze the overlay error mapping policy for transport failures.

---

## M2 — Proxy behavior

1. Extend `/api/*` proxy support for the async queue/job routes.
2. Forward method, path, query string, headers, and body without changing semantics.
3. Strip hop-by-hop headers where required.
4. Preserve upstream statuses when they still communicate useful job state.
5. Make proxy timeout configurable for long-running requests.

---

## M3 — Streaming bridge

1. Detect whether upstream exposes SSE or websocket-style status updates.
2. Proxy stream responses without buffering them into memory unnecessarily.
3. Keep reconnect behavior browser-friendly.
4. Ensure client disconnects close upstream resources cleanly.

---

## M4 — Error mapping and observability

1. Map upstream connection failures to `upstream_unavailable`.
2. Map upstream timeouts to `upstream_timeout`.
3. Preserve upstream application errors where they are meaningful for job state.
4. Add structured logging for:
   - correlation id
   - `job_id`
   - upstream route
   - upstream status
   - request duration

---

## M5 — Verification

1. Add direct tests for job submission proxying.
2. Add direct tests for polling and status routes.
3. Add direct tests for upstream timeout and unavailable handling.
4. Add direct tests for optional stream pass-through when supported.
5. Run the full test suite and fix any coverage gaps.
