from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn

from forge_overlay.app import create_app
from forge_overlay.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description="forge-overlay development server")
    parser.add_argument(
        "--site-dir",
        type=Path,
        default=os.environ.get("FORGE_SITE_DIR", "public"),
        help="Path to site output directory (default: public)",
    )
    parser.add_argument(
        "--overlay-dir",
        type=Path,
        default=os.environ.get("FORGE_OVERLAY_DIR", "overlay"),
        help="Path to overlay assets directory (default: overlay)",
    )
    parser.add_argument(
        "--api-upstream",
        type=str,
        default=os.environ.get("FORGE_API_UPSTREAM", "http://127.0.0.1:3000"),
        help="Upstream URL for /api/* proxy (default: http://127.0.0.1:3000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("FORGE_HOST", "127.0.0.1"),
        help="Bind host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FORGE_PORT", "8080")),
        help="Bind port (default: 8080)",
    )
    args = parser.parse_args()

    config = Config(
        site_dir=Path(args.site_dir),
        overlay_dir=Path(args.overlay_dir),
        api_upstream=args.api_upstream,
        host=args.host,
        port=args.port,
    )

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


if __name__ == "__main__":
    main()
