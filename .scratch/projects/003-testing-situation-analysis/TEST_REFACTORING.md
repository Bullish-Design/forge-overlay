# TEST_REFACTORING

Date: 2026-04-25

This document lists required changes to bring `forge-overlay` to full, reliable verification coverage for intended functionality.

## Required Changes

1. Add CLI/unit tests for `main.py`.
1. Create `tests/test_main.py` and validate:
1. Default values when no CLI args or env vars are set.
1. Env var values when CLI args are omitted.
1. CLI args overriding env vars.
1. `FORGE_PORT` parse behavior for invalid values (expected failure path or explicit validation if implemented).
1. `uvicorn.run()` receives expected host/port/log_level and app object.

1. Expand app-level route tests in `tests/test_integration.py`.
1. Add explicit SSE contract test:
1. Open `/ops/events`, trigger `POST /internal/rebuild`, assert emitted `{"type":"rebuilt"}` payload.
1. Add `/ops/{path}` security and error tests:
1. Traversal attempt (for example `/ops/../../secret`) returns `403`.
1. Missing overlay asset returns `404`.
1. Add `/about/?x=1` redirect assertion keeps query string (`/about?x=1`).
1. Add API route method coverage for `HEAD` and `OPTIONS`.
1. Add app lifespan test ensuring client shutdown runs during TestClient context exit.

1. Expand proxy correctness tests in `tests/test_proxy.py`.
1. Assert request-side hop-by-hop headers are stripped before upstream call.
1. Assert `Host` header is not forwarded.
1. Assert response-side hop-by-hop headers are removed before returning to caller.
1. Add upstream exception path tests (timeout/connect failure) and enforce expected external behavior.
1. If no explicit behavior is currently defined, implement deterministic behavior in `proxy.py` (recommended: `502 Bad Gateway` with plain error payload) and test it.

1. Expand injection middleware branch coverage in `tests/test_inject.py`.
1. Add ASGI `scope["type"] != "http"` passthrough test.
1. Add multi-chunk response body injection test (`more_body=True` flow).
1. Add `content-type` variant test with charset (`text/html; charset=utf-8`).
1. Add case-insensitivity test for `</HEAD>` marker handling.

1. Expand static handler edge-path tests in `tests/test_static_handler.py`.
1. Add test for `build_response()` media-type assignment on known and unknown extensions.
1. Add test for `resolve_file()` `OSError` handling branch via monkeypatching `Path.resolve`.
1. Add explicit test for `_is_within` false branch through controlled candidate path behavior.

1. Improve coverage policy in `pyproject.toml`.
1. Add `--cov-fail-under=90` (or higher once tests are completed).
1. Add `--no-cov-on-fail` for clearer CI behavior.
1. Resolve `module-not-measured` warning by tightening coverage start/import order in test invocation and validating warning-free runs.

1. Add manual verification scripts for integration contracts not fully captured in unit tests.
1. Add `scripts/test_smoke_kiln_integration.sh`:
1. Starts overlay.
1. Runs `kiln dev --no-serve --on-rebuild ...`.
1. Verifies webhook-to-SSE chain on file change.
1. Add `scripts/test_smoke_proxy_error_modes.sh`:
1. Verifies expected behavior for upstream unavailable cases.

1. Wire required checks into CI.
1. Ensure CI runs:
1. `uv sync --all-extras`
1. `uv run ruff check src tests`
1. `uv run ruff format --check src tests`
1. `uv run mypy src/forge_overlay/`
1. `uv run pytest -v --cov=forge_overlay --cov-report=term-missing`
1. Enforce failure on coverage threshold and linter/type failures.

## Completion Criteria

1. Test count increases to cover all branches listed above.
1. `main.py` and `app.py` reach high branch confidence with explicit negative-case testing.
1. Coverage warning is removed and coverage threshold is enforced.
1. All checks pass locally in `devenv` and in CI.
1. Kiln webhook-to-SSE behavior is validated by repeatable smoke script.
