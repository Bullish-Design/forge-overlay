from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Config:
    """Runtime configuration for forge-overlay."""

    # Directory containing the built site output (kiln's --output dir)
    site_dir: Path = field(default_factory=lambda: Path("public"))

    # Directory containing overlay static assets (ops.js, ops.css)
    overlay_dir: Path = field(default_factory=lambda: Path("overlay"))

    # Upstream URL for /api/* proxy (obsidian-agent)
    api_upstream: str = "http://127.0.0.1:3000"

    # Host and port for the overlay server itself
    host: str = "127.0.0.1"
    port: int = 8080
