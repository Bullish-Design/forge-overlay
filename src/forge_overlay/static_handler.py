from __future__ import annotations

import mimetypes
from pathlib import Path

from starlette.responses import FileResponse, Response


# Resolution order (matches kiln dev-server behavior):
#   1. Exact file match
#   2. <path>.html
#   3. <path>/index.html
#   4. 404.html fallback (if present)

def resolve_file(site_dir: Path, url_path: str) -> Path | None:
    """Resolve a URL path to a file on disk. Returns None if not found."""
    # Normalize: strip leading slash, reject path traversal
    clean = url_path.strip("/")

    # Candidate paths in priority order
    if clean == "":
        candidates = [site_dir / "index.html"]
    else:
        candidates = [
            site_dir / clean,
            site_dir / f"{clean}.html",
            site_dir / clean / "index.html",
        ]

    for candidate in candidates:
        # Resolve symlinks and verify the file is inside site_dir
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_file() and _is_within(resolved, site_dir.resolve()):
            return resolved

    return None


def build_response(file_path: Path) -> Response:
    """Build a FileResponse with the correct content type."""
    content_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=file_path, media_type=content_type)


def build_404(site_dir: Path) -> Response:
    """Return a 404 response, using custom 404.html if available."""
    custom = site_dir / "404.html"
    if custom.is_file():
        return FileResponse(path=custom, status_code=404, media_type="text/html")
    return Response(content="Not Found", status_code=404, media_type="text/plain")


def _is_within(path: Path, parent: Path) -> bool:
    """Check that path is inside parent (prevents directory traversal)."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
