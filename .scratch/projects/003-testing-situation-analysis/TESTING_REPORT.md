# Testing Report: forge-overlay

Date: 2026-04-25

## 1. Executive Summary

The project has **26 passing tests** at **81% line coverage**. The existing test suite is a solid foundation covering all happy paths for the core modules. However, there are meaningful gaps: `main.py` has 0% coverage, several security/error branches in `app.py` and `static_handler.py` are untested, there is no end-to-end SSE integration test, proxy failure modes are unhandled in both code and tests, and the coverage configuration has a warning that undermines signal quality.

The analysis documents (`TESTING_ANALYSIS.md` and `TEST_REFACTORING.md`) are accurate in their findings. This report validates their claims against the actual code and test output, adds concrete line-level analysis, identifies additional issues they missed, and provides a prioritized action plan.

---

## 2. Verified Facts from Test Run

| Metric | Value |
|--------|-------|
| Python | 3.13.12 |
| pytest | 9.0.3 |
| Tests collected | 26 |
| Tests passed | 26 |
| Tests failed | 0 |
| Total statements | 196 |
| Statements missed | 38 |
| Line coverage | 81% |
| Coverage warning | `module-not-measured` on `forge_overlay` |
| `--cov-fail-under` | **Not set** |

---

## 3. Module-by-Module Analysis

### 3.1 `main.py` — 0% coverage (20/20 lines missed)

**Assessment: High risk. The entire CLI entrypoint is untested.**

This module handles:
- Argument parsing with `argparse` (5 flags)
- Environment variable fallback (`FORGE_SITE_DIR`, `FORGE_OVERLAY_DIR`, `FORGE_API_UPSTREAM`, `FORGE_HOST`, `FORGE_PORT`)
- `Config` construction from parsed args
- `uvicorn.run()` invocation

**What needs testing:**
1. Default values when no args or env vars are set
2. Env var override of defaults
3. CLI args override of env vars
4. `FORGE_PORT` with non-integer value (currently `int()` will raise `ValueError` — no graceful handling)
5. That `create_app` receives a correctly constructed `Config`
6. That `uvicorn.run` receives expected `host`, `port`, `log_level`

**Testing approach:** Monkeypatch `sys.argv`, `os.environ`, and `uvicorn.run` to capture calls without actually starting a server. This is straightforward and does not require integration-level tests.

**Bug found:** If `FORGE_PORT` is set to a non-numeric string, `int(os.environ.get("FORGE_PORT", "8080"))` raises an unhandled `ValueError` at import/parse time. This should either be caught with a useful error message or left as-is with a test documenting the behavior.

### 3.2 `app.py` — 80% coverage (12 lines missed)

**Lines missed and what they cover:**

| Lines | Function | What's untested |
|-------|----------|-----------------|
| 36-40 | `sse_events` | The SSE endpoint handler and its `event_generator` closure |
| 49-50 | `overlay_static` | The `403 Forbidden` response for path traversal |
| 52 | `overlay_static` | The `404 Not Found` response for missing overlay files |
| 57 | `api_proxy` | The proxy handler itself (tested indirectly through `test_proxy.py` but not via app routing) |
| 67 | `site_static` | Query string preservation during trailing-slash redirect |
| 89-92 | `lifespan` | The `httpx.AsyncClient.aclose()` shutdown cleanup |

**Assessment: Medium-high risk.**

The SSE endpoint (`/ops/events`) is the core of the rebuild notification system and has no integration test proving that `POST /internal/rebuild` → SSE stream actually works end-to-end. The `TESTING_ANALYSIS.md` correctly identifies this as a gap.

The overlay static handler's security branch (traversal → 403) is untested at the app level. While the static handler's own `resolve_file` has a traversal test, the `/ops/{path}` route in `app.py` has its own independent traversal check via `relative_to()` that is never exercised.

The lifespan cleanup is important for resource management — an unclosed `httpx.AsyncClient` can leak connections.

### 3.3 `static_handler.py` — 87% coverage (4 lines missed)

**Lines missed:**

| Lines | What's untested |
|-------|-----------------|
| 34-35 | `OSError` branch in `resolve_file` (the `except OSError: continue`) |
| 61-62 | `_is_within` returning `False` via `ValueError` (path outside parent) |

**Assessment: Low-medium risk.**

The `OSError` branch is defensive code for filesystem errors during `Path.resolve()`. It's hard to trigger naturally but can be tested with monkeypatching.

The `_is_within` false branch is the core of the path traversal defense. While the `test_path_traversal_blocked` test exercises the overall `resolve_file` flow with a traversal path, it doesn't directly hit the `_is_within` false return because `Path.resolve()` normalizes `/../..` paths before `_is_within` is called — the traversal is actually caught by `is_file()` returning `False` for the resolved path (which points outside the fixture). The `_is_within` check acts as a second defense layer that isn't triggered by the current test.

**To verify this claim:** The path `/../../../etc/passwd` resolves to `/etc/passwd`. On a system where `/etc/passwd` exists, `resolved.is_file()` returns `True`, but `_is_within` correctly rejects it. The current test passes because `is_file()` happens to fail first on the test filesystem. This means the traversal defense has a test that passes for the wrong reason — `_is_within` is never actually the line that blocks it in the test.

**Recommendation:** Add a test that creates a file outside `site_dir` and verifies `resolve_file` returns `None` even though the file exists. This would exercise the `_is_within` false branch directly.

### 3.4 `inject.py` — 95% coverage (2 lines missed)

**Lines missed:**

| Lines | What's untested |
|-------|-----------------|
| 17-18 | `scope["type"] != "http"` passthrough branch |

**Assessment: Low risk.**

This is the early-return path for non-HTTP ASGI scopes (websocket, lifespan). It's important for correctness — if the middleware crashed on lifespan events, the app wouldn't start — but it's exercised implicitly every time `TestClient` starts up (lifespan scope). The reason it shows as uncovered is likely the `module-not-measured` coverage timing issue.

**Additional untested behaviors:**
- Multi-chunk response bodies (`more_body=True` intermediate chunks)
- `Content-Type: text/html; charset=utf-8` (with parameters)
- Case-insensitive `</HEAD>` matching (the code does `body.lower().find()`, but no test verifies this)

### 3.5 `events.py` — 100% coverage

**Assessment: Well tested.** All four tests (publish-to-subscriber, no-subscribers, cleanup, multiple-subscribers) are solid. The `asyncio.sleep(0)` after task completion in `test_subscriber_cleanup` is a smart way to let the generator's `finally` block run.

### 3.6 `proxy.py` — 100% coverage

**Assessment: Line coverage is complete but behavioral coverage has gaps.**

What's tested:
- GET forwarding with URL construction
- POST body forwarding
- Query string forwarding

What's NOT tested (even though lines are covered):
- Hop-by-hop header stripping on requests (no test sends a `Connection` header and verifies it's removed)
- `Host` header removal (no test verifies `Host` is absent from upstream request)
- Response hop-by-hop header filtering (no test has upstream return `Transfer-Encoding` and verifies it's stripped)
- Upstream failure behavior (timeout, connection refused) — `proxy.py` has **no error handling** for `httpx` exceptions

**This is the most significant finding that the analysis documents correctly identify but understate.** If `obsidian-agent` is down, `proxy_request` will raise an unhandled `httpx.ConnectError` that propagates up as a 500 Internal Server Error with a stack trace. This is not just a test gap — it's a code gap. The proxy should catch `httpx.HTTPError` and return a `502 Bad Gateway`.

### 3.7 `config.py` — 100% coverage

**Assessment: Trivial module, correctly covered.** The frozen dataclass with defaults is simple and correct.

---

## 4. Validation of Analysis Documents

### `TESTING_ANALYSIS.md` — Accuracy Review

| Claim | Verdict | Notes |
|-------|---------|-------|
| 81% total coverage, 26 tests passing | **Confirmed** | Exact match with test run |
| `main.py` at 0% | **Confirmed** | |
| `app.py` at 80% | **Confirmed** | |
| `static_handler.py` at 87% | **Confirmed** | |
| `inject.py` at 95% | **Confirmed** | |
| Non-HTTP scope passthrough untested | **Confirmed** | Lines 17-18 |
| No CLI tests for arg precedence | **Confirmed** | |
| No SSE integration test | **Confirmed** | Critical gap |
| No overlay traversal defense test | **Confirmed** | Lines 49-50 in app.py |
| No proxy header policy tests | **Confirmed** | 100% line coverage masks this |
| No upstream failure tests | **Confirmed** | Code gap too, not just test gap |
| No lifespan cleanup test | **Confirmed** | Lines 89-92 |
| No `--cov-fail-under` | **Confirmed** | |
| `module-not-measured` warning | **Confirmed** | Visible in test output |

**Bottom line:** The analysis is accurate across every claim. No false positives or exaggerations found.

### `TEST_REFACTORING.md` — Completeness Review

The refactoring plan is well-structured and covers all the gaps identified in the analysis. Additional observations:

**Strengths:**
- Correctly identifies the need for `502 Bad Gateway` behavior in proxy failure cases
- Proposes concrete test scenarios, not vague "add more tests"
- Includes CI wiring and coverage threshold as part of the plan
- Smoke test scripts for manual verification are pragmatic

**Gaps in the refactoring plan:**

1. **`_is_within` test gap is subtler than described.** The plan says "Add explicit test for `_is_within` false branch through controlled candidate path behavior" but doesn't note that the existing traversal test passes for the wrong reason (see 3.3 above). The fix needs a test with a real file outside `site_dir`, not just a different path string.

2. **Missing: `build_response()` is never directly tested.** It's exercised indirectly via integration tests, but there's no unit test verifying correct MIME type assignment. The plan mentions this but buries it as one sub-item.

3. **Missing: redirect with query string.** The plan mentions `?x=1` but the redirect test in `test_integration.py` currently only tests `/about/` → `/about` without a query string. Line 67 in `app.py` (query preservation) is confirmed uncovered.

4. **Missing: `POST /internal/rebuild` ignores request body.** The handler calls `broker.publish(json.dumps({"type": "rebuilt"}))` — it constructs the event payload itself rather than forwarding the webhook body. This is correct per design ("treat webhook input as a trigger, not a schema-heavy API") but there's no test verifying that a malformed body doesn't cause an error. Not a bug, but worth a defensive test.

5. **No mention of `AsyncGenerator` type annotation.** The `events.py` `subscribe()` method uses `AsyncGenerator[str]` (single type param) which is the Python 3.13+ syntax. If Python compatibility matters, this should be noted. Currently fine since the project requires `>=3.13`.

6. **The numbered list formatting in both documents is broken.** Every item uses `1.` which renders correctly in some Markdown renderers (auto-incrementing) but reads poorly in plain text and is ambiguous about nesting. This is cosmetic but worth noting for maintainability.

---

## 5. Risk-Prioritized Action Plan

### Priority 1: Code fixes (bugs/missing behavior)

| # | Action | Risk mitigated |
|---|--------|----------------|
| 1a | Add error handling in `proxy.py` for `httpx.HTTPError` → return `502 Bad Gateway` | Unhandled exception on upstream failure |
| 1b | Add graceful handling for invalid `FORGE_PORT` in `main.py` | `ValueError` crash on bad env var |

### Priority 2: High-value tests (security + core contract)

| # | Action | What it proves |
|---|--------|----------------|
| 2a | SSE integration test: `POST /internal/rebuild` → event on `/ops/events` | The core rebuild notification pipeline works end-to-end |
| 2b | Overlay path traversal test at app level (`/ops/../../secret` → 403) | The security boundary in `app.py` works |
| 2c | `_is_within` test with a real out-of-tree file | Path traversal defense in `static_handler.py` is effective |
| 2d | Proxy upstream failure test (connection refused → 502) | Graceful degradation when obsidian-agent is down |
| 2e | `main.py` tests for CLI/env/default precedence | The entrypoint constructs config correctly |

### Priority 3: Branch coverage completion

| # | Action | Lines covered |
|---|--------|--------------|
| 3a | Missing overlay asset → 404 test | `app.py:52` |
| 3b | Trailing-slash redirect with query string | `app.py:67` |
| 3c | Proxy hop-by-hop header stripping assertions | `proxy.py` behavioral coverage |
| 3d | Inject middleware: non-HTTP scope passthrough | `inject.py:17-18` |
| 3e | Inject middleware: `</HEAD>` case-insensitive test | `inject.py:_inject` |
| 3f | Inject middleware: `text/html; charset=utf-8` | `inject.py` content-type matching |
| 3g | `build_response()` MIME type assignment | `static_handler.py` |
| 3h | `resolve_file()` OSError branch via monkeypatch | `static_handler.py:34-35` |

### Priority 4: Infrastructure

| # | Action | Benefit |
|---|--------|---------|
| 4a | Add `--cov-fail-under=90` to `pyproject.toml` | Prevent coverage regressions |
| 4b | Resolve `module-not-measured` warning | Clean coverage signal |
| 4c | Add lifespan shutdown test | Verify `httpx.AsyncClient` is closed |
| 4d | Wire all checks into CI | Automated quality gate |

---

## 6. Estimated Test Count After Completion

| File | Current tests | New tests needed | Total |
|------|--------------|-----------------|-------|
| `test_main.py` | 0 | 5-6 | 5-6 |
| `test_static_handler.py` | 8 | 3-4 | 11-12 |
| `test_inject.py` | 4 | 3-4 | 7-8 |
| `test_events.py` | 4 | 0 | 4 |
| `test_proxy.py` | 3 | 4-5 | 7-8 |
| `test_integration.py` | 7 | 4-5 | 11-12 |
| **Total** | **26** | **19-24** | **45-50** |

Expected coverage after completion: **92-96%** (remaining uncovered lines would be the `uvicorn.run()` call itself and any defensive `assert` statements).

---

## 7. Conclusion

The analysis documents are thorough and accurate — every claim they make is validated by the actual code and test output. The existing 26 tests are well-written with good patterns (mock transports, async test structure, fixture isolation). The gaps are real but bounded: ~20 additional tests would close them all.

The single most important action is **adding error handling to `proxy.py`** — this is not a test gap but a code gap that would cause a stack trace in production when the upstream is unavailable. The second most important action is the **SSE integration test**, which would verify the core value proposition of the service (rebuild notifications reaching the browser).

The `TESTING_ANALYSIS.md` and `TEST_REFACTORING.md` documents are well-structured, accurate, and actionable. The only material weakness is that the `_is_within` traversal test is subtler than described — the existing test passes for the wrong reason, and the fix requires a more careful test setup than the plan implies.
