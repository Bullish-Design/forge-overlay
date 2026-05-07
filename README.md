# forge-overlay

Browser-facing HTTP edge service for Forge v2.

## What It Does
- Serves built site output with clean-URL routing.
- Injects overlay assets into HTML responses.
- Proxies agent APIs to an upstream service:
  - `/api/*` -> upstream `/api/*`
  - `/v1/*` -> upstream `/v1/*`

## Run
```bash
python -m forge_overlay.main \
  --site-dir public \
  --overlay-dir overlay \
  --api-upstream http://127.0.0.1:3000
```

## Configuration
- `--site-dir` / `FORGE_SITE_DIR`: site output directory (default: `public`)
- `--overlay-dir` / `FORGE_OVERLAY_DIR`: overlay asset directory (default: `overlay`)
- `--api-upstream` / `FORGE_API_UPSTREAM`: upstream base URL (default: `http://127.0.0.1:3000`)
- `--api-proxy-timeout-s` / `FORGE_API_PROXY_TIMEOUT_S`: upstream request timeout in seconds for `/api/*` and `/v1/*` (default: `600.0`)
- `--host` / `FORGE_HOST`: bind host (default: `127.0.0.1`)
- `--port` / `FORGE_PORT`: bind port (default: `8080`)

Timeout behavior uses a fast connect timeout (`10s`) and long read/write/pool timeout (`--api-proxy-timeout-s`) for long-running job workflows.

## Job API Through Overlay
Submit a job:
```bash
curl -X POST http://127.0.0.1:8080/v1/jobs \
  -H 'content-type: application/json' \
  -d '{"op":"apply","payload":{"patch":"..."}}'
```

Poll a job:
```bash
curl http://127.0.0.1:8080/v1/jobs/<job_id>
```

List recent jobs:
```bash
curl 'http://127.0.0.1:8080/v1/jobs?limit=10'
```

## Error Mapping Contract
- Upstream timeout: `504` + `{"error":"upstream_timeout"}`
- Other upstream transport failures: `502` + `{"error":"upstream_unavailable"}`
- Upstream HTTP responses (including 4xx/5xx) are passed through unchanged.
