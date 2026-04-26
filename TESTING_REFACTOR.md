# TESTING_REFACTOR

Date: 2026-04-25
Source review: `.scratch/projects/003-testing-situation-analysis/TESTING_REPORT.md`

## Goal

Provide a concrete, step-by-step implementation plan to move `forge-overlay` from partial verification to near-complete functional, error-path, and integration coverage, including a demo/example vault workflow.

This plan assumes the current state:
- 26 tests passing
- ~81% line coverage
- Typer-based CLI in `src/forge_overlay/main.py`

## Definition of "Tested In Full" for This Repo

For this service, "in full" means:
1. Every externally-visible contract has at least one direct test.
2. Every security/error branch has a direct test.
3. CLI behavior is tested for defaults, env vars, and flag overrides.
4. Rebuild webhook -> SSE event pipeline is verified end-to-end.
5. Proxy behavior is verified for success, headers, and upstream failure.
6. Demo vault content is used in automated integration tests.
7. CI enforces lint, typing, tests, and coverage thresholds.

## Target End State

1. 45-55 tests total.
2. >=95% coverage with `--cov-fail-under=95`.
3. No `module-not-measured` warning in normal CI runs.
4. Repeatable demo-vault integration test (automated).
5. Optional kiln-backed smoke test (manual/CI optional job).

---

## Step 0 - Baseline and Branching

1. Create branch:
   ```bash
   git checkout -b test-refactor-full-verification
   ```
2. Capture baseline output:
   ```bash
   devenv shell -- uv run pytest -v --cov=forge_overlay --cov-report=term-missing
   ```
3. Save baseline in `.scratch/projects/003-testing-situation-analysis/BASELINE_TEST_OUTPUT.md`.

Deliverable:
- Baseline report committed for before/after comparison.

---

## Step 1 - Add Demo Vault Fixtures

Create fixture tree:
```text
tests/fixtures/demo_vault/
  source/
    index.md
    notes/
      day-1.md
      day-2.md
    projects/
      forge.md
  built_site/
    index.html
    notes/
      day-1.html
      day-2.html
    projects/
      forge.html
    404.html
tests/fixtures/demo_overlay/
  ops.js
  ops.css
```

Implementation notes:
1. `source/` represents human-editable vault input.
2. `built_site/` is static output that overlay serves in tests.
3. Keep HTML deterministic and simple.
4. Include at least one page with `<head>` to validate injection.

Also add helper:
```text
tests/helpers/demo_fixtures.py
```
with functions:
1. `copy_demo_site(tmp_path) -> Path`
2. `copy_demo_overlay(tmp_path) -> Path`
3. `copy_demo_vault_source(tmp_path) -> Path`

Deliverable:
- Reusable demo fixtures used by integration/e2e tests.

---

## Step 2 - Refactor `conftest.py` for Reuse

Update `tests/conftest.py`:
1. Keep existing `tmp_site`, `tmp_overlay`.
2. Add `demo_site`, `demo_overlay`, `demo_vault_source` fixtures from `tests/helpers/demo_fixtures.py`.
3. Add `demo_config` fixture:
   - `site_dir=demo_site`
   - `overlay_dir=demo_overlay`

Deliverable:
- Any test can run against minimal fixtures or realistic demo vault fixtures.

---

## Step 3 - CLI Test Coverage (Typer)

Create:
```text
tests/test_main.py
```

Use:
1. `typer.testing.CliRunner`
2. monkeypatch for `forge_overlay.main.create_app`
3. monkeypatch for `forge_overlay.main.uvicorn.run`

Required test cases:
1. `test_cli_uses_defaults_when_no_env_or_flags`
2. `test_cli_reads_env_vars`
3. `test_cli_flags_override_env_vars`
4. `test_cli_invalid_port_fails_cleanly`
5. `test_cli_invokes_uvicorn_with_expected_args`

Expected behavior:
1. exit code `0` on valid input.
2. non-zero exit on invalid `--port`.
3. `Config` fields passed exactly as expected.

Deliverable:
- `main.py` moves from ~0% to high confidence coverage.

---

## Step 4 - Harden and Test Proxy Failure Behavior

### 4A. Code change (required)

In `src/forge_overlay/proxy.py`, add explicit handling for upstream errors:
1. Catch `httpx.HTTPError`.
2. Return a deterministic `502 Bad Gateway` response.
3. Keep current success-path streaming behavior unchanged.

Recommended response:
1. status code: `502`
2. content type: `application/json`
3. body: `{"error":"upstream_unavailable"}`

### 4B. Test expansion

Update `tests/test_proxy.py` with:
1. `test_strips_hop_by_hop_request_headers`
2. `test_does_not_forward_host_header`
3. `test_strips_hop_by_hop_response_headers`
4. `test_upstream_connect_error_returns_502`
5. `test_upstream_timeout_returns_502`

Deliverable:
- Proxy has graceful degradation and full behavioral assertions.

---

## Step 5 - Complete `app.py` Branch Coverage

Update `tests/test_integration.py` (and split into focused files if it gets too large).

Add tests:
1. `/ops/events` SSE contract test:
   - open event stream
   - POST `/internal/rebuild`
   - assert `{"type":"rebuilt"}` event received
2. `/ops/{path}` traversal returns `403`
3. `/ops/{path}` missing file returns `404`
4. redirect query preservation:
   - `/about/?x=1` -> `/about?x=1`
5. route-level proxy methods:
   - `HEAD` and `OPTIONS` on `/api/{path}`
6. malformed rebuild payload does not crash:
   - still returns `204` (trigger-only semantics)

Deliverable:
- `app.py` error/security/lifecycle branches are directly tested.

---

## Step 6 - Cover Remaining Unit Branches

### `tests/test_static_handler.py`
Add:
1. MIME type assertion for `build_response()` known extension (`.css`).
2. MIME type assertion for unknown extension fallback.
3. `Path.resolve` `OSError` branch via monkeypatch.
4. `_is_within` false branch with real out-of-tree file.

### `tests/test_inject.py`
Add:
1. `scope["type"] != "http"` passthrough test.
2. multi-chunk body (`more_body=True`) injection test.
3. `text/html; charset=utf-8` content-type test.
4. uppercase `</HEAD>` marker test.

Deliverable:
- Remaining low-level branches are explicitly covered.

---

## Step 7 - Demo Vault End-to-End Test Suite

Create:
```text
tests/test_demo_vault_e2e.py
```

Use demo fixtures (`demo_site`, `demo_overlay`, `demo_config`) and verify:
1. Root page renders demo vault home content.
2. Nested clean URLs resolve demo pages:
   - `/notes/day-1`
   - `/projects/forge`
3. 404 page from demo site is served + injected.
4. CSS asset from demo site is not injected.
5. Rebuild trigger still emits SSE event while serving demo content.

Deliverable:
- Realistic content topology is continuously tested, not just synthetic minimal fixtures.

---

## Step 8 - Optional Kiln-Backed Integration (External)

Add external/integration test marker and test:
```text
tests/test_kiln_external.py
```

Behavior:
1. Skip unless `kiln` binary exists.
2. Start overlay server pointed at temp output dir.
3. Run:
   ```bash
   kiln dev --no-serve --on-rebuild http://127.0.0.1:<port>/internal/rebuild --input <demo_vault_source> --output <temp_public>
   ```
4. Modify a demo vault file.
5. Assert SSE event observed.

Also add script:
```text
scripts/test_smoke_kiln_demo_vault.sh
```

Deliverable:
- Optional true integration with real kiln behavior.

---

## Step 9 - Coverage and Pytest Policy Hardening

Update `pyproject.toml`:
1. Add coverage threshold:
   - `--cov-fail-under=95`
2. Add:
   - `--cov-branch`
   - `--no-cov-on-fail`
3. Add `[tool.coverage.run]`:
   - `source = ["forge_overlay"]`
   - `branch = true`
4. Add `[tool.coverage.report]`:
   - `show_missing = true`
   - `skip_covered = false`

If `module-not-measured` persists:
1. Ensure no early import side-effects in test bootstrap.
2. Run pytest through a single stable command in CI (avoid duplicate coverage args).
3. Fail CI on coverage warnings until resolved.

Deliverable:
- Coverage becomes an enforced signal, not informational.

---

## Step 10 - CI Workflow Enforcement

Create or update `.github/workflows/test.yml`:
1. setup Python 3.13
2. install `uv`
3. `uv sync --all-extras`
4. run:
   - `uv run ruff check src tests`
   - `uv run ruff format --check src tests`
   - `uv run mypy src/forge_overlay/`
   - `uv run pytest -v`

Optional separate jobs:
1. `external-kiln-smoke` (manual trigger or nightly).
2. `coverage-report` upload artifact.

Deliverable:
- Full testing gate enforced before merge.

---

## Step 11 - Implementation Order (Commit Plan)

Use this order to keep PRs reviewable and green:
1. Fixtures + conftest refactor.
2. CLI tests (`test_main.py`).
3. Proxy error handling + proxy tests.
4. App integration branch tests + SSE.
5. Static/inject branch tests.
6. Demo vault e2e suite.
7. Coverage policy changes.
8. CI updates.
9. External kiln test + smoke script.

Commit after each step with focused messages.

---

## Step 12 - Final Exit Criteria

All must be true:
1. `devenv shell -- uv run ruff check src tests` passes.
2. `devenv shell -- uv run mypy src/forge_overlay/` passes.
3. `devenv shell -- uv run pytest -v` passes.
4. Coverage >=95% with enforced fail-under.
5. Demo vault e2e tests pass in normal CI.
6. External kiln smoke test is runnable and documented.
7. No untriaged coverage warnings.

When all seven pass, the repository can be considered fully verified for intended behavior.
