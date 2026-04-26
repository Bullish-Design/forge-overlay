from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import uvicorn

from forge_overlay.app import create_app
from forge_overlay.config import Config

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def serve(
    site_dir: Annotated[
        Path,
        typer.Option(
            "--site-dir",
            envvar="FORGE_SITE_DIR",
            help="Path to site output directory (default: public)",
        ),
    ] = Path("public"),
    overlay_dir: Annotated[
        Path,
        typer.Option(
            "--overlay-dir",
            envvar="FORGE_OVERLAY_DIR",
            help="Path to overlay assets directory (default: overlay)",
        ),
    ] = Path("overlay"),
    api_upstream: Annotated[
        str,
        typer.Option(
            "--api-upstream",
            envvar="FORGE_API_UPSTREAM",
            help="Upstream URL for /api/* proxy (default: http://127.0.0.1:3000)",
        ),
    ] = "http://127.0.0.1:3000",
    host: Annotated[
        str,
        typer.Option(
            "--host",
            envvar="FORGE_HOST",
            help="Bind host (default: 127.0.0.1)",
        ),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(
            "--port",
            envvar="FORGE_PORT",
            help="Bind port (default: 8080)",
        ),
    ] = 8080,
) -> None:
    """Run the forge-overlay development server."""

    config = Config(
        site_dir=site_dir,
        overlay_dir=overlay_dir,
        api_upstream=api_upstream,
        host=host,
        port=port,
    )

    app = create_app(config)
    uvicorn.run(app, host=config.host, port=config.port, log_level="info")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
