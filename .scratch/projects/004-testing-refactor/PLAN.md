# Testing Refactor Plan

Updated: 2026-04-25

Source analysis: `.scratch/projects/003-testing-situation-analysis/`

---

## 1. Current State

### 1.1 Baseline Numbers

- 26 tests passing across 5 test files
- 81% line coverage (196 statements, 38 missed)
- All lint (`ruff`), format (`ruff format`), and type (`mypy --strict`) checks pass
- Coverage emits a `module-not-measured` warning on `forge_overlay`
- No `--cov-fail-under` threshold enforced

### 1.2 Coverage by Module

| Module | Stmts | Miss | Cover | Missed Lines | What's Untested |
|--------|-------|------|-------|--------------|-----------------|
| `__init__.py` | 0 | 0 | 100% | — | — |
| `config.py` | 10 | 0 | 100% | — | — |
| `events.py` | 20 | 0 | 100% | — | — |
| `proxy.py` | 15 | 0 | 100% | — | Line coverage complete but behavioral gaps (see 2.3) |
| `inject.py` | 41 | 2 | 95% | 17-18 | Non-HTTP scope passthrough |
| `static_handler.py` | 31 | 4 | 87% | 34-35, 61-62 | `OSError` branch, `_is_within` false branch |
| `app.py` | 59 | 12 | 80% | 36-40, 49-50, 52, 57, 67, 89-92 | SSE endpoint, overlay traversal/404, proxy route, query-string redirect, lifespan cleanup |
| `main.py` | 20 | 20 | 0% | 1-80 | Entire CLI entrypoint |

### 1.3 What Works Well Today

- Static URL resolution (root, clean URLs, directory index, missing page)
- HTML injection for standard HTML and non-HTML responses
- Event broker fan-out and subscriber cleanup
- Proxy GET/POST/query forwarding via `httpx.MockTransport`
- App-level route smoke tests for rebuild endpoint, static serving, redirects

---

## 2. Gaps and Findings

### 2.1 Code Bugs (not just test gaps)

**2.1.1 Proxy has no error handling for upstream failures**

`proxy.py` does not catch `httpx.HTTPError`. If `obsidian-agent` is down, the unhandled `httpx.ConnectError` propagates as a 500 Internal Server Error with a stack trace.

Required fix: catch `httpx.HTTPError` and return `502 Bad Gateway` with `{"error": "upstream_unavailable"}`.

### 2.2 `main.py` — 0% Coverage

The CLI uses Typer with `envvar=` parameters, so argument precedence (CLI > env > default) is handled by the framework. Testing approach:

- Use `typer.testing.CliRunner` to invoke the CLI
- Monkeypatch `forge_overlay.main.uvicorn` to capture `.run()` calls without starting a server
- Monkeypatch `forge_overlay.main.create_app` to capture the `Config` argument

Note: Typer handles invalid `--port` values with its own validation, so the test expectation is a non-zero exit with Typer's error output, not an unhandled `ValueError`.

### 2.3 Proxy — 100% Line Coverage Masks Behavioral Gaps

All lines are covered, but no test verifies:

- Hop-by-hop headers are stripped from requests before forwarding upstream
- `Host` header is removed before forwarding
- Hop-by-hop headers in the upstream response are stripped before returning to the client
- Upstream connection failure or timeout behavior

### 2.4 `app.py` — Untested Branches

| Lines | Handler | What's untested |
|-------|---------|-----------------|
| 36-40 | `sse_events` | SSE endpoint + event generator (no end-to-end rebuild → SSE test) |
| 49-50 | `overlay_static` | Path traversal → 403 |
| 52 | `overlay_static` | Missing overlay file → 404 |
| 57 | `api_proxy` | Proxy route exercised at app level |
| 67 | `site_static` | Query string preserved during trailing-slash redirect |
| 89-92 | `lifespan` | `httpx.AsyncClient.aclose()` on shutdown |

### 2.5 `static_handler.py` — Traversal Test Passes for the Wrong Reason

The existing `test_path_traversal_blocked` sends `/../../../etc/passwd`. `Path.resolve()` normalizes this to `/etc/passwd`. On the test filesystem, `is_file()` returns `False` for the resolved path because the temp fixture doesn't contain `/etc/passwd`, so `_is_within` is never reached. The `_is_within` false branch (lines 61-62) remains uncovered.

Fix: create a real file outside `site_dir` and verify `resolve_file` returns `None` even though the file exists on disk.

### 2.6 `inject.py` — Minor Branch Gaps

- Non-HTTP scope passthrough (lines 17-18): implicitly exercised by lifespan during `TestClient` startup, but coverage doesn't see it due to `module-not-measured` timing
- No test for `text/html; charset=utf-8` content-type variant
- No test for case-insensitive `</HEAD>` marker
- No test for multi-chunk body responses (`more_body=True`)

### 2.7 Infrastructure Gaps

- No `--cov-fail-under` — coverage regressions can land silently
- `module-not-measured` warning — coverage plugin starts after initial imports, so `forge_overlay` module-level code isn't measured. Needs `[tool.coverage.run] source` config.
- No CI workflow enforcing any checks

---

## 3. Definition of Done

All of the following must be true:

1. Every externally-visible route has at least one direct test.
2. Every security/error branch has a direct test.
3. CLI behavior is tested for defaults, env vars, and flag overrides.
4. Rebuild webhook → SSE event pipeline is verified end-to-end.
5. Proxy behavior is verified for success, headers, and upstream failure.
6. Demo vault content with realistic nesting is used in integration tests.
7. `devenv shell -- uv run pytest -v` passes with >=90% coverage enforced.
8. `devenv shell -- uv run ruff check src tests` passes.
9. `devenv shell -- uv run mypy src/forge_overlay/` passes.
10. No coverage warnings in normal test runs.
11. `demo/` directory contains real vault content with scripts for running, generating injected output, and cleanup.
12. `uv run forge-generate` produces viewable injected HTML in `demo/generated/`.

Target: 45-55 tests total, >=90% line coverage with `--cov-fail-under=90`.

---

## 4. Implementation Steps

### Step 1 — Baseline Capture

1. Create branch: `git checkout -b test-refactor`
2. Run and save baseline output:
   ```bash
   devenv shell -- uv run pytest -v --cov=forge_overlay --cov-report=term-missing
   ```
3. Commit baseline snapshot.

Deliverable: before/after comparison anchor.

---

### Step 2 — Demo Vault Directory Tree

Create a `demo/` directory at the repo root containing real vault source, pre-built site output, overlay assets, and scripts.

#### 2A. Directory structure

```
demo/
  vault/
    index.md
    notes/
      day-1.md
      day-2.md
    projects/
      forge.md
  site/
    index.html
    notes/
      day-1.html
      day-2.html
    projects/
      forge.html
    style.css
    logo.png
    404.html
  overlay/
    ops.js
    ops.css
  generated/          ← created by generate-demo.sh, .gitignored
    index.html
    notes/
      day-1.html
      ...
  scripts/
    run-demo.sh
    generate-demo.sh
    clean-demo.sh
```

Add `demo/generated/` to `.gitignore`.

#### 2B. Vault source files (`demo/vault/`)

These represent the human-editable Obsidian vault input. They are not directly served by forge-overlay but establish the content authoring side of the pipeline.

`demo/vault/index.md`:
```markdown
---
title: Vault Home
---
# Welcome to the Demo Vault

This is a demonstration vault for forge-overlay development and testing.
```

`demo/vault/notes/day-1.md`:
```markdown
---
title: Day 1
---
# Day 1 Notes

First day of working on the forge project.
```

`demo/vault/notes/day-2.md`:
```markdown
---
title: Day 2
---
# Day 2 Notes

Continued work on forge integration.
```

`demo/vault/projects/forge.md`:
```markdown
---
title: Forge
---
# Forge Project

The forge orchestrator coordinates kiln, obsidian-agent, and the overlay.
```

#### 2C. Built site output (`demo/site/`)

These are the static HTML files that forge-overlay actually serves. They represent the output of `kiln dev` building the vault source.

`demo/site/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Vault Home</title>
</head>
<body>
  <h1>Welcome to the Demo Vault</h1>
  <p>This is a demonstration vault for forge-overlay development and testing.</p>
  <nav>
    <ul>
      <li><a href="/notes/day-1">Day 1</a></li>
      <li><a href="/notes/day-2">Day 2</a></li>
      <li><a href="/projects/forge">Forge</a></li>
    </ul>
  </nav>
</body>
</html>
```

`demo/site/notes/day-1.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Day 1</title>
</head>
<body>
  <h1>Day 1 Notes</h1>
  <p>First day of working on the forge project.</p>
</body>
</html>
```

`demo/site/notes/day-2.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Day 2</title>
</head>
<body>
  <h1>Day 2 Notes</h1>
  <p>Continued work on forge integration.</p>
</body>
</html>
```

`demo/site/projects/forge.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Forge</title>
</head>
<body>
  <h1>Forge Project</h1>
  <p>The forge orchestrator coordinates kiln, obsidian-agent, and the overlay.</p>
</body>
</html>
```

`demo/site/404.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>404 - Not Found</title>
</head>
<body>
  <h1>Page not found</h1>
  <p>The page you requested does not exist.</p>
  <a href="/">Return home</a>
</body>
</html>
```

`demo/site/style.css`:
```css
:root {
  --fg: #1a1a1a;
  --bg: #fafafa;
}
body {
  font-family: system-ui, sans-serif;
  color: var(--fg);
  background: var(--bg);
  max-width: 42rem;
  margin: 2rem auto;
  padding: 0 1rem;
  line-height: 1.6;
}
a { color: #2563eb; }
```

`demo/site/logo.png`: a minimal valid PNG (create as binary — 8-byte PNG header + minimal IHDR/IDAT/IEND chunks). In practice, use any small PNG file or generate one in a script.

#### 2D. Overlay assets (`demo/overlay/`)

`demo/overlay/ops.js`:
```javascript
(() => {
  const es = new EventSource("/ops/events");
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === "rebuilt") {
      console.log("[forge-overlay] Rebuild detected, reloading...");
      location.reload();
    }
  };
  es.onerror = () => {
    console.warn("[forge-overlay] SSE connection lost, will retry...");
  };
})();
```

`demo/overlay/ops.css`:
```css
#ops-indicator {
  position: fixed;
  bottom: 8px;
  right: 8px;
  padding: 4px 8px;
  font-size: 12px;
  background: rgba(0, 0, 0, 0.6);
  color: #0f0;
  border-radius: 4px;
  font-family: monospace;
  z-index: 99999;
  pointer-events: none;
}
```

#### 2E. Scripts (`demo/scripts/`)

`demo/scripts/run-demo.sh`:
```bash
#!/usr/bin/env bash
# Run the forge-overlay server against the demo vault content.
#
# Usage:
#   ./demo/scripts/run-demo.sh [--port PORT]
#
# Requires: devenv shell or activated venv with forge-overlay installed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SITE_DIR="$DEMO_DIR/site"
OVERLAY_DIR="$DEMO_DIR/overlay"
PORT="${1:-8080}"

if [[ "$1" == "--port" ]]; then
  PORT="${2:-8080}"
fi

echo "=== forge-overlay demo ==="
echo "  site:    $SITE_DIR"
echo "  overlay: $OVERLAY_DIR"
echo "  port:    $PORT"
echo ""
echo "  http://127.0.0.1:$PORT/"
echo "  http://127.0.0.1:$PORT/notes/day-1"
echo "  http://127.0.0.1:$PORT/projects/forge"
echo ""
echo "  POST http://127.0.0.1:$PORT/internal/rebuild to simulate a rebuild."
echo "  GET  http://127.0.0.1:$PORT/ops/events for SSE stream."
echo ""

exec uv run forge-overlay \
  --site-dir "$SITE_DIR" \
  --overlay-dir "$OVERLAY_DIR" \
  --port "$PORT"
```

`demo/scripts/generate-demo.sh`:
```bash
#!/usr/bin/env bash
# Generate the injected demo site output for offline viewing.
#
# Reads demo/site/ HTML files, applies the forge-overlay injection
# (ops.js + ops.css tags), and writes the result to demo/generated/.
# Non-HTML files are copied unchanged.
#
# Usage:
#   ./demo/scripts/generate-demo.sh
#
# After running, open demo/generated/index.html in a browser to inspect
# the injected output. CSS/JS assets are referenced via absolute paths
# (/ops/ops.css, /ops/ops.js) so they won't resolve from file:// — use
# the run-demo.sh server for full fidelity, or inspect the HTML source.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

SITE_DIR="$DEMO_DIR/site"
OVERLAY_DIR="$DEMO_DIR/overlay"
OUT_DIR="$DEMO_DIR/generated"

# Clean previous output
rm -rf "$OUT_DIR"

echo "Generating injected demo site..."
echo "  source:  $SITE_DIR"
echo "  overlay: $OVERLAY_DIR"
echo "  output:  $OUT_DIR"
echo ""

# Use the Python injection pipeline directly
uv run python -c "
import shutil
from pathlib import Path
from forge_overlay.inject import SNIPPET

site = Path('$SITE_DIR')
out = Path('$OUT_DIR')

for src_file in site.rglob('*'):
    if src_file.is_dir():
        continue
    rel = src_file.relative_to(site)
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    if src_file.suffix == '.html':
        html = src_file.read_bytes()
        marker = b'</head>'
        idx = html.lower().find(marker)
        if idx != -1:
            html = html[:idx] + SNIPPET.encode() + html[idx:]
        dest.write_bytes(html)
        print(f'  injected: {rel}')
    else:
        shutil.copy2(src_file, dest)
        print(f'  copied:   {rel}')

# Also copy overlay assets into generated/ops/ for self-contained viewing
ops_dir = out / 'ops'
ops_dir.mkdir(parents=True, exist_ok=True)
overlay = Path('$OVERLAY_DIR')
for f in overlay.iterdir():
    if f.is_file():
        shutil.copy2(f, ops_dir / f.name)
        print(f'  overlay:  ops/{f.name}')

print()
print(f'Done. View: {out}/index.html')
"
```

`demo/scripts/clean-demo.sh`:
```bash
#!/usr/bin/env bash
# Clean generated/cached files from the demo directory.
#
# Removes:
#   - demo/generated/ (output of generate-demo.sh)
#   - __pycache__ dirs
#   - .pytest_cache dirs
#
# Does NOT remove the demo vault source, site, or overlay content.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$DEMO_DIR/.." && pwd)"

echo "Cleaning generated files..."

# Generated demo output
if [ -d "$DEMO_DIR/generated" ]; then
  rm -rf "$DEMO_DIR/generated"
  echo "  removed: demo/generated/"
fi

# Demo directory caches
find "$DEMO_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DEMO_DIR" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Repo-wide generated outputs
rm -rf "$REPO_DIR/.pytest_cache"
rm -rf "$REPO_DIR/.mypy_cache"
rm -rf "$REPO_DIR/.ruff_cache"
rm -f  "$REPO_DIR/.coverage"
rm -rf "$REPO_DIR/htmlcov"

echo "Done."
```

#### 2F. `pyproject.toml` script entries

Add project scripts for the demo and cleanup workflows:

```toml
[project.scripts]
forge-overlay = "forge_overlay.main:main"

# These are shell scripts, not Python entrypoints — wire them through
# [tool.hatch.envs] or as documented CLI recipes. See below for the
# recommended approach using pyproject.toml [project.scripts] alternatives.
```

Since `[project.scripts]` only supports Python entrypoints, wire the demo/clean commands as **`uv run` script aliases** using `[tool.uv.scripts]` (if supported) or document them as make-style targets. The most reliable approach for this repo is to add them to `pyproject.toml` under a custom tool table that the README can reference, and create thin Python wrappers:

Add to `pyproject.toml`:

```toml
[tool.forge-overlay.scripts]
demo = "demo/scripts/run-demo.sh"
generate = "demo/scripts/generate-demo.sh"
clean = "demo/scripts/clean-demo.sh"
```

And add the executable Python script entrypoints for `uv run` convenience:

Create `src/forge_overlay/_scripts.py`:
```python
"""Convenience script entrypoints for demo and cleanup."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    """Walk up to find the repo root (contains pyproject.toml)."""
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Cannot find repo root")


def _run_script(name: str, extra_args: bool = False) -> None:
    """Run a shell script from demo/scripts/."""
    script = _repo_root() / "demo" / "scripts" / name
    args = ["bash", str(script)]
    if extra_args:
        args.extend(sys.argv[1:])
    sys.exit(subprocess.call(args))


def run_demo() -> None:
    """Run the demo server."""
    _run_script("run-demo.sh", extra_args=True)


def generate_demo() -> None:
    """Generate injected demo site output to demo/generated/."""
    _run_script("generate-demo.sh")


def clean_demo() -> None:
    """Clean generated files."""
    _run_script("clean-demo.sh")
```

Then update `[project.scripts]` in `pyproject.toml`:
```toml
[project.scripts]
forge-overlay = "forge_overlay.main:main"
forge-demo = "forge_overlay._scripts:run_demo"
forge-generate = "forge_overlay._scripts:generate_demo"
forge-clean = "forge_overlay._scripts:clean_demo"
```

This gives four commands available via `uv run`:
- `uv run forge-overlay` — run the server
- `uv run forge-demo` — run the demo server with pre-configured paths
- `uv run forge-generate` — apply injection to demo site, write output to `demo/generated/` for viewing
- `uv run forge-clean` — remove `demo/generated/` and caches

#### 2G. Test fixtures wired to demo directory

Add to `tests/conftest.py`:

```python
import shutil

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


@pytest.fixture
def demo_site(tmp_path: Path) -> Path:
    """Copy demo vault site output to a temp directory for isolated testing."""
    dest = tmp_path / "site"
    shutil.copytree(DEMO_DIR / "site", dest)
    return dest


@pytest.fixture
def demo_overlay(tmp_path: Path) -> Path:
    """Copy demo overlay assets to a temp directory for isolated testing."""
    dest = tmp_path / "overlay"
    shutil.copytree(DEMO_DIR / "overlay", dest)
    return dest


@pytest.fixture
def demo_config(demo_site: Path, demo_overlay: Path) -> Config:
    """Config using demo vault fixtures."""
    return Config(site_dir=demo_site, overlay_dir=demo_overlay)
```

Tests get isolated copies of the real demo content via `shutil.copytree` into `tmp_path`, so tests can modify files without polluting the repo.

Keep existing `tmp_site`, `tmp_overlay`, `config` fixtures unchanged — unit tests continue using the minimal fixtures.

Deliverable: `demo/` directory with real vault content; `conftest.py` fixtures that copy it for test isolation; `uv run forge-demo`, `uv run forge-generate`, and `uv run forge-clean` commands wired into pyproject.toml; `demo/generated/` in `.gitignore`.

---

### Step 3 — Proxy Error Handling (Code Fix + Tests)

#### 3A. Code change: `src/forge_overlay/proxy.py`

Add error handling around the upstream request:

```python
async def proxy_request(...) -> StreamingResponse | Response:
    ...
    try:
        upstream_resp = await client.request(...)
    except httpx.HTTPError:
        return Response(
            content='{"error":"upstream_unavailable"}',
            status_code=502,
            media_type="application/json",
        )
    ...
```

Note: the return type widens to `StreamingResponse | Response`. Update the type annotation accordingly.

#### 3B. New tests in `tests/test_proxy.py`

5 new test cases:

1. `test_strips_hop_by_hop_request_headers` — send a request with `Connection: keep-alive` header, assert it's absent from the upstream request
2. `test_does_not_forward_host_header` — send a request, assert `host` is not in the upstream request headers
3. `test_strips_hop_by_hop_response_headers` — upstream returns `Transfer-Encoding: chunked`, assert it's absent from the proxy response
4. `test_upstream_connect_error_returns_502` — use a mock transport that raises `httpx.ConnectError`, assert 502 with `{"error": "upstream_unavailable"}`
5. `test_upstream_timeout_returns_502` — use a mock transport that raises `httpx.ReadTimeout`, assert 502

Deliverable: proxy has graceful degradation and full behavioral assertions.

---

### Step 4 — CLI Tests

Create `tests/test_main.py`.

Testing approach:
- `typer.testing.CliRunner` invokes the CLI without starting a real server
- Monkeypatch `forge_overlay.main.create_app` to capture the `Config` it receives
- Monkeypatch the `uvicorn` module (as imported in `forge_overlay.main`) to capture `.run()` calls

Note on monkeypatching: `main.py` does `import uvicorn` at module level, so the correct target is `forge_overlay.main.uvicorn` (the module object), not `forge_overlay.main.uvicorn.run` (which would try to patch through the real module). Replace `uvicorn.run` with a mock on that module:

```python
mock_uvicorn_run = MagicMock()
monkeypatch.setattr("forge_overlay.main.uvicorn", MagicMock(run=mock_uvicorn_run))
```

5 test cases:

1. `test_defaults_with_no_args_or_env` — invoke with no args, no env vars set. Assert `Config` has default values (`site_dir=Path("public")`, `port=8080`, etc.).
2. `test_env_vars_override_defaults` — set `FORGE_SITE_DIR=/tmp/vault`, `FORGE_PORT=9090` via monkeypatch. Assert `Config` picks them up.
3. `test_cli_flags_override_env_vars` — set env var AND pass `--port 7070`. Assert CLI flag wins.
4. `test_invalid_port_exits_nonzero` — invoke with `--port abc`. Assert exit code != 0 (Typer handles this).
5. `test_uvicorn_receives_config_values` — assert `uvicorn.run()` is called with the correct `host`, `port`, `log_level`.

Deliverable: `main.py` moves from 0% to high-confidence coverage.

---

### Step 5 — App Integration Branch Coverage

Expand `tests/test_integration.py` with new test cases. Use both `config` (minimal) and `demo_config` (realistic) fixtures.

#### 5A. SSE end-to-end contract test

This is the most important missing test. Approach:

```python
import threading
import time
import json

def test_rebuild_triggers_sse_event(demo_config: Config) -> None:
    app = create_app(demo_config)
    received_events: list[str] = []

    def sse_listener():
        """Connect to SSE in a background thread."""
        with TestClient(app) as client:
            with client.stream("GET", "/ops/events") as resp:
                for line in resp.iter_lines():
                    if line.startswith("data:"):
                        received_events.append(line.removeprefix("data:").strip())
                        break  # Got one event, done

    listener = threading.Thread(target=sse_listener, daemon=True)
    listener.start()
    time.sleep(0.1)  # Let SSE connection establish

    # Trigger rebuild
    with TestClient(app) as client:
        resp = client.post("/internal/rebuild")
        assert resp.status_code == 204

    listener.join(timeout=2.0)
    assert len(received_events) == 1
    assert json.loads(received_events[0]) == {"type": "rebuilt"}
```

Note: SSE with `TestClient` may require the same app instance across threads since the `EventBroker` is scoped to `create_app()`. If `TestClient.stream` doesn't work directly with `EventSourceResponse`, an alternative is to test the broker wiring separately by accessing the broker from the app's closure (via a test helper that exposes it). Document whichever approach works during implementation.

#### 5B. Overlay static security and error tests

```
test_overlay_traversal_returns_403       — GET /ops/../../etc/passwd → 403
test_overlay_missing_file_returns_404    — GET /ops/nonexistent.js → 404
```

#### 5C. Redirect query string preservation

```
test_trailing_slash_redirect_preserves_query — GET /about/?x=1 → 301 to /about?x=1
```

#### 5D. Malformed rebuild payload

```
test_rebuild_with_empty_body_returns_204    — POST /internal/rebuild with no body → 204
test_rebuild_with_garbage_body_returns_204  — POST /internal/rebuild with "garbage" → 204
```

These confirm trigger-only semantics — the handler ignores the request body entirely.

#### 5E. Demo vault content tests (using `demo_config`)

These tests exercise real vault content through the full app stack:

```
test_demo_root_serves_vault_home           — GET / → 200, contains "Welcome to the Demo Vault"
test_demo_nested_clean_url_notes           — GET /notes/day-1 → 200, contains "Day 1 Notes"
test_demo_nested_clean_url_projects        — GET /projects/forge → 200, contains "Forge Project"
test_demo_404_serves_custom_page           — GET /nonexistent → 404, contains "Page not found"
test_demo_css_asset_not_injected           — GET /style.css → 200, no "ops.js" in body
test_demo_binary_asset_served              — GET /logo.png → 200
test_demo_html_pages_are_injected          — GET /notes/day-1 → "ops.js" in body
```

#### 5F. Lifespan cleanup test

Approach: monkeypatch `httpx.AsyncClient.__init__` to capture the instance, then verify it's closed after `TestClient` context exit.

```python
def test_lifespan_closes_http_client(config: Config, monkeypatch) -> None:
    captured_client = None
    original_init = httpx.AsyncClient.__init__

    def tracking_init(self, *args, **kwargs):
        nonlocal captured_client
        original_init(self, *args, **kwargs)
        captured_client = self

    monkeypatch.setattr(httpx.AsyncClient, "__init__", tracking_init)

    app = create_app(config)
    with TestClient(app):
        assert captured_client is not None
        assert not captured_client.is_closed

    assert captured_client.is_closed
```

Deliverable: all `app.py` branches tested; SSE contract verified; demo vault content tested end-to-end.

---

### Step 6 — Static Handler Branch Coverage

Add to `tests/test_static_handler.py`:

#### 6A. `_is_within` false branch with real out-of-tree file

```python
def test_traversal_blocked_for_existing_file_outside_site(self, tmp_path: Path) -> None:
    """Prove _is_within blocks access even when the file exists on disk."""
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text("<html><head></head><body>OK</body></html>")

    # Create a file OUTSIDE site_dir
    secret = tmp_path / "secret.txt"
    secret.write_text("sensitive data")

    # Attempt to resolve a path that escapes site_dir
    result = resolve_file(site_dir, "/../secret.txt")
    assert result is None
```

#### 6B. `build_response()` MIME type tests

```python
def test_build_response_css_mime_type(self, tmp_site: Path) -> None:
    result = resolve_file(tmp_site, "/style.css")
    assert result is not None
    resp = build_response(result)
    assert resp.media_type == "text/css"

def test_build_response_unknown_extension(self, tmp_path: Path) -> None:
    unknown = tmp_path / "data.xyz"
    unknown.write_text("stuff")
    resp = build_response(unknown)
    assert resp.media_type is None  # mimetypes returns None for unknown
```

#### 6C. `OSError` branch via monkeypatch

```python
def test_resolve_file_handles_oserror(self, tmp_site: Path, monkeypatch) -> None:
    """Verify OSError during Path.resolve() is caught and skipped."""
    original_resolve = Path.resolve

    def exploding_resolve(self, strict=False):
        if "about" in str(self):
            raise OSError("simulated filesystem error")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", exploding_resolve)
    # Should return None gracefully, not raise
    result = resolve_file(tmp_site, "/about")
    # All candidates containing "about" will OSError; falls through to None
    assert result is None
```

Deliverable: `static_handler.py` reaches full branch coverage.

---

### Step 7 — Injection Middleware Branch Coverage

Add to `tests/test_inject.py`:

1. **Non-HTTP scope passthrough:**
   ```python
   async def test_non_http_scope_passthrough(self) -> None:
       """Verify non-HTTP scopes (websocket, lifespan) pass through unchanged."""
       inner_called = False

       async def mock_app(scope, receive, send):
           nonlocal inner_called
           inner_called = True

       middleware = InjectMiddleware(mock_app)
       await middleware({"type": "lifespan"}, None, None)
       assert inner_called
   ```

2. **Content-type with charset:**
   ```python
   def test_injects_with_charset_content_type(self) -> None:
       """text/html; charset=utf-8 should still trigger injection."""
       client = TestClient(_make_app())
       resp = client.get("/")
       assert "ops.js" in resp.text
   ```
   (Note: this may already pass since `HTMLResponse` sets `text/html; charset=utf-8` — but the explicit test documents the contract.)

3. **Case-insensitive `</HEAD>` marker:**
   ```python
   def test_injects_with_uppercase_head_tag(self) -> None:
       app = _make_app("<html><HEAD></HEAD><body>hi</body></html>")
       client = TestClient(app)
       resp = client.get("/")
       assert "ops.js" in resp.text
   ```

Deliverable: `inject.py` reaches full branch coverage.

---

### Step 8 — Coverage and Pytest Configuration

Update `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-q --cov=forge_overlay --cov-report=term-missing --cov-fail-under=90 --no-cov-on-fail"
testpaths = ["tests"]

[tool.coverage.run]
source = ["forge_overlay"]
branch = true

[tool.coverage.report]
show_missing = true
skip_covered = false
```

Key decisions:
- `--cov-fail-under=90` not 95 — `main.py` contains `uvicorn.run()` and `typer.Typer()` wiring that's impractical to cover without starting a real server. 90% is honest without requiring `# pragma: no cover` suppressions.
- `branch = true` in `[tool.coverage.run]` — enables branch coverage measurement. Do NOT also add `--cov-branch` to addopts (redundant).
- `source = ["forge_overlay"]` — fixes the `module-not-measured` warning by telling coverage to measure the package from the start.

Deliverable: coverage becomes an enforced quality gate.

---

### Step 9 — CI Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: cachix/install-nix-action@v27
      - uses: cachix/cachix-action@v15
        with:
          name: devenv
      - run: nix profile install nixpkgs#devenv
      - run: devenv shell -- uv sync --all-extras
      - run: devenv shell -- uv run ruff check src tests
      - run: devenv shell -- uv run ruff format --check src tests
      - run: devenv shell -- uv run mypy src/forge_overlay/
      - run: devenv shell -- uv run pytest -v
```

All commands run through `devenv shell` to match local development.

Deliverable: automated quality gate on every push and PR.

---

### Step 10 — Commit Order

Land changes in this order, keeping the branch green after each commit:

| # | Content | Why this order |
|---|---------|----------------|
| 1 | Proxy error handling code fix (`proxy.py`) | Production code fix lands first and independently |
| 2 | `demo/` directory tree + scripts (run/generate/clean) + `_scripts.py` + pyproject.toml script entries + `.gitignore` update | Foundation for all demo-based tests |
| 3 | `conftest.py` demo fixtures (`demo_site`, `demo_overlay`, `demo_config`) | Wires demo content into test infrastructure |
| 4 | CLI tests (`test_main.py`) | Independent module, no deps on other new tests |
| 5 | Proxy behavioral tests (`test_proxy.py`) | Builds on commit 1 |
| 6 | App integration tests + demo vault e2e (`test_integration.py`) | Uses demo fixtures from commits 2-3 |
| 7 | Static handler branch tests (`test_static_handler.py`) | Independent unit tests |
| 8 | Inject middleware branch tests (`test_inject.py`) | Independent unit tests |
| 9 | Coverage config changes (`pyproject.toml`) | Only enforce threshold after tests are in place |
| 10 | CI workflow (`.github/workflows/test.yml`) | Last, after all tests pass locally |

---

## 5. Expected End State

| Metric | Before | After |
|--------|--------|-------|
| Test count | 26 | 45-55 |
| Line coverage | 81% | >=90% |
| `--cov-fail-under` | not set | 90 |
| `module-not-measured` warning | present | resolved |
| `main.py` coverage | 0% | ~80%+ |
| `app.py` coverage | 80% | ~95%+ |
| SSE e2e test | none | 1+ |
| Proxy failure test | none | 2+ |
| Traversal defense tests | weak | direct |
| CI enforcement | none | full |
| Demo vault tests | none | 7+ tests with real content |
| Demo run script | none | `uv run forge-demo` |
| Demo generate script | none | `uv run forge-generate` |
| Demo clean script | none | `uv run forge-clean` |

---

## 6. Out of Scope

- **kiln-fork external integration test** — deferred until `kiln` binary is available and the integration is actively being developed. The rebuild webhook is fully testable without kiln by POSTing directly to `/internal/rebuild`.
- **obsidian-agent external integration** — the proxy is tested with mock transports; real upstream testing is out of scope.
- **Performance or load testing** — not needed for a development server.
