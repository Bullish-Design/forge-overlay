# Decisions

Updated: 2026-04-27

---

## D-001 — Keep queue logic out of the overlay  [RESOLVED]

**Decision: `forge-overlay` remains transport-only.**

The overlay proxies queue and job endpoints, but does not create, persist, retry, or schedule jobs.

**Rationale:**
- Preserves a clean responsibility boundary
- Avoids duplicating upstream queue state
- Keeps the overlay focused on browser-facing HTTP behavior

**Rejected: Embed queue orchestration in overlay**
That would couple the edge service to business logic and make failure handling harder to reason about.

---

## D-002 — Default job lifecycle pattern  [RESOLVED]

**Decision: Prefer submit fast, poll later, stream optionally.**

The overlay should expect job submission to return quickly with a `job_id` or equivalent token, after which the browser can poll a status endpoint or attach to a stream.

**Rationale:**
- Prevents the browser from blocking on long-running work
- Matches the operational shape of async job systems
- Makes the overlay a simple bridge rather than a coordinator

**Rejected: Synchronous wait-for-completion as the default**
That creates poor UX and makes timeout handling fragile.

---

## D-003 — Streaming support  [RESOLVED]

**Decision: Support streaming as an optional proxy path.**

If `obsidian-agent` exposes SSE or websocket status updates, the overlay should pass them through with minimal transformation.

**Rationale:**
- Keeps browser reconnection semantics intact
- Avoids duplicating stream framing or event semantics
- Allows the upstream service to choose its own streaming mechanism

**Rejected: Convert streaming into overlay-owned polling**
That would throw away useful real-time semantics and create unnecessary latency.

---

## D-004 — Upstream error mapping  [RESOLVED]

**Decision: Normalize transport failures, preserve meaningful upstream app errors.**

Overlay maps connection failures and timeouts to stable errors such as `upstream_unavailable` and `upstream_timeout`, while preserving upstream status codes when they still communicate useful job state.

**Rationale:**
- Browser clients should not depend on raw transport exceptions
- Stable error names simplify UI handling and logs
- Upstream application errors can still be useful and should not be flattened unnecessarily

---

## D-005 — Timeout policy  [RESOLVED]

**Decision: Timeouts are configurable and should favor non-blocking flows.**

The proxy timeout must be adjustable so long-running operations can be tuned per environment.

**Rationale:**
- Development, staging, and production may need different limits
- Async work should generally finish outside the request path
- A fixed hardcoded timeout would be too brittle

---

## D-006 — Observability scope  [RESOLVED]

**Decision: Log correlation hints, not payloads.**

The overlay should record request correlation data, `job_id`, upstream route, status, and duration where available, but avoid logging sensitive bodies or headers.

**Rationale:**
- Async queue bugs are difficult to debug without trace context
- Logging full payloads creates a privacy and security risk
- Correlation data gives enough signal for most operational issues

---

## D-007 — Client compatibility goal  [RESOLVED]

**Decision: Browser-facing behavior wins over internal convenience.**

The proxy contract should be shaped for browser clients and production UI behavior, even if that means more explicit handling in the overlay.

**Rationale:**
- The overlay is the public edge
- UI stability matters more than implementation simplicity here
- The contract should survive upstream evolution as long as the browser semantics remain stable
