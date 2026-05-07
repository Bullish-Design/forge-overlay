# Improvement Recommendations for Queue Refactor V2

## 1. Tighten connect timeout separately from read timeout

The guide uses `httpx.Timeout(config.api_proxy_timeout_s)` which sets all four timeout components (connect, read, write, pool) to the same value. A 600s connect timeout is excessively generous — connection establishment should fail fast.

**Recommendation:** Use `httpx.Timeout(config.api_proxy_timeout_s, connect=10.0)` to keep connect timeout tight while allowing long reads for job polling.

## 2. Explicitly match method set for `/v1/` route

The guide says "same method set" for `/v1/` but doesn't verify the current set. The existing `/api/{path:path}` route uses `methods=["GET", "POST", "PUT", "PATCH", "DELETE"]`. The `/v1/` route definition should copy this list exactly, ideally via a shared constant to prevent drift.

**Recommendation:** Extract the method list into a module-level constant in `app.py`:

```python
_PROXY_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
```

Use it for both route definitions.

## 3. README update can be deferred

Step 9 (README) is low-risk and doesn't affect functionality. If time is constrained, defer it to a follow-up commit without blocking the functional PR.

## 4. Consider passing full path instead of prefix parameter

The guide adds `upstream_prefix="/api"` to `proxy_request()`. An alternative is to have each route handler build the upstream path directly, since the handler already knows its prefix. Both approaches work — the guide's approach is fine and arguably more explicit — but the alternative avoids adding a parameter whose only purpose is to reconstruct information the caller already has.

Example alternative:

```python
# In app.py handler
async def v1_proxy(request):
    path = request.path_params["path"]
    upstream_path = f"/v1/{path}"
    return await proxy_request(request, config.api_upstream, client, upstream_path)
```

This is a stylistic preference, not a correctness issue. The guide's `upstream_prefix` approach is equally valid.
