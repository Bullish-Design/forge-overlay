# Execution Queue

Updated: 2026-04-24

All decisions resolved. Ready to execute. Work items in order.

---

## M1 — kiln-fork

1. Fork `github.com/otaleghani/kiln` at tag `v0.9.5` into `Bullish-Design/kiln-fork`
2. In `internal/cli/dev.go`:
   - Add `--no-serve` bool flag (skip `server.Serve(...)` call when set)
   - Add `--on-rebuild <url>` string flag
   - In the watcher's `OnRebuild` callback: if `--on-rebuild` URL is set, POST
     `{"type":"rebuilt"}` with a short timeout (5s), log error but don't fail the build
3. Smoke test the flags manually
4. Run `go test ./...` — all existing tests must pass
5. Tag `v0.9.5-forge.1`
6. Open upstream PR against `otaleghani/kiln` with the two flags

---

## M2 — forge-overlay

1. `uv init forge-overlay --lib`
   - deps: `starlette`, `sse-starlette`, `httpx`, `uvicorn[standard]`
   - dev deps: `pytest`, `pytest-asyncio`, `httpx` (test client)

2. `forge_overlay/static_handler.py`
   - `StaticHandler(output_dir)`: ASGI app
   - Clean URL logic: try `path + ".html"`, then `path/index.html`, then 404
   - Custom 404: serve `output_dir/404.html` if it exists

3. `forge_overlay/inject.py`
   - `InjectionMiddleware(app, enabled=True)`: Starlette middleware
   - Buffer response body only when `Content-Type: text/html`
   - Insert `<!-- ops-overlay --><link rel="stylesheet" href="/ops/ops.css"><script src="/ops/ops.js" defer></script>` before `</head>` (case-insensitive)
   - Recalculate `Content-Length` after injection
   - Passthrough for all other content types

4. `forge_overlay/events.py`
   - `SSEBroker`: holds `set[asyncio.Queue]`, `subscribe()`, `unsubscribe()`, `broadcast(data)`
   - `/ops/events` endpoint: `EventSourceResponse` (sse-starlette) backed by a queue

5. `forge_overlay/proxy.py`
   - `ProxyHandler(target_url, timeout)`: ASGI app
   - Forward request with original method, headers, body to `target_url + request.url.path`
   - Forward response status + headers + body back

6. `forge_overlay/app.py`
   - `create_app(config)` factory
   - Route table:
     - `/internal/rebuild` POST → `broker.broadcast('{"type":"rebuilt"}')`
     - `/ops/events` GET → SSE endpoint
     - `/ops/{path:path}` → `StaticFiles(directory=config.overlay_dir)`
     - `/api/{path:path}` → `ProxyHandler(config.agent_url)`
     - `/{path:path}` → `InjectionMiddleware(StaticHandler(config.output_dir))`

7. Unit tests (`tests/`)
   - `test_inject.py`: HTML gets snippet, non-HTML passthrough, no `</head>` passthrough
   - `test_static.py`: clean URLs, index.html fallback, 404 fallback
   - `test_events.py`: SSE client receives broadcast after POST to /internal/rebuild
   - `test_proxy.py`: request headers forwarded, response proxied correctly

8. Integration test with kiln-fork binary:
   - Start kiln-fork in watch mode with `--on-rebuild http://localhost:8080/internal/rebuild`
   - Connect SSE client to `/ops/events`
   - Edit a vault file
   - Assert SSE client receives `{"type":"rebuilt"}` within 2 seconds

---

## M3 — forge (Python orchestrator)

1. `uv init forge --app`
   - deps: `pydantic-settings`, `typer`, `httpx`
   - dev deps: `pytest`

2. `forge_cli/config.py`
   - `ForgeConfig(BaseSettings)`:
     ```
     vault_dir, output_dir, overlay_dir, port=8080
     agent_port=8081, agent_llm_model, agent_vault_dir
     kiln_theme, kiln_font, kiln_lang, kiln_site_name
     ```
   - Loads from `forge.yaml` + `FORGE_*` env overrides
   - Derives `agent_url = f"http://127.0.0.1:{agent_port}"`
   - Derives `on_rebuild_url = f"http://127.0.0.1:{port}/internal/rebuild"`

3. `forge_cli/processes.py`
   - `ProcessManager`: starts subprocesses, streams logs with prefixes, waits for health
   - `wait_for_http(url, timeout)`: polls URL until 200 or timeout
   - `start_overlay(config)` → uvicorn subprocess
   - `start_agent(config)` → obsidian-agent subprocess with env vars
   - `start_kiln(config)` → kiln-fork subprocess with flags

4. `forge_cli/commands.py` (typer app)
   - `forge dev`: overlay → agent (health gate) → kiln; Ctrl-C shuts all down
   - `forge generate`: kiln generate only
   - `forge serve`: overlay only (no kiln watcher)
   - `forge init`: mkdir vault, write forge.yaml with defaults

5. `docker/docker-compose.yml` (updated):
   ```yaml
   services:
     tailscale: ...
     kiln-fork:
       image: kiln-fork:local
       command: kiln watch --no-serve --on-rebuild http://127.0.0.1:8080/internal/rebuild ...
       volumes: [forge-vault, forge-public]
       network_mode: service:tailscale
     forge-overlay:
       image: forge-overlay:local
       volumes: [forge-public:/output:ro, ./static:/overlay:ro]
       network_mode: service:tailscale
     obsidian-agent:
       image: obsidian-agent:local
       volumes: [forge-vault:/data/vault]
       network_mode: service:tailscale
   ```

6. `docker/kiln-fork.Dockerfile` (Go binary build)
7. `docker/forge-overlay.Dockerfile` (Python + forge-overlay package)

8. Smoke test: `forge dev` from empty vault → browser loads site → overlay injected

---

## M4 — End-to-End Validation

1. `forge dev` cold start from empty vault — confirm site loads, overlay assets present
2. Edit `vault/index.md` — confirm SSE received, browser reloads, new content visible
3. Submit instruction via overlay UI — confirm LLM runs, vault file changes, reload occurs
4. POST `/api/undo` — confirm vault reverts, rebuild fires, reload occurs
5. `docker compose up` from scratch — confirm same behavior in containers
6. `git diff upstream/main` on kiln-fork — confirm ≤50 lines changed
7. Confirm obsidian-ops and obsidian-agent at same commit as before this project started
8. Archive `Bullish-Design/forge` Go repo (rename to `forge-go-archive` or similar)
