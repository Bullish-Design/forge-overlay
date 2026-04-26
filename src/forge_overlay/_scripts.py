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
