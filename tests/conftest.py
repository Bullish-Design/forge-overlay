from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from forge_overlay.config import Config

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


@pytest.fixture
def tmp_site(tmp_path: Path) -> Path:
    """Create a minimal site directory with test files."""
    # index page
    (tmp_path / "index.html").write_text("<html><head></head><body>Home</body></html>")
    # A nested page with clean URL support
    (tmp_path / "about.html").write_text("<html><head></head><body>About</body></html>")
    # A directory with index
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog" / "index.html").write_text("<html><head></head><body>Blog</body></html>")
    # Non-HTML asset
    (tmp_path / "style.css").write_text("body { margin: 0; }")
    # Custom 404
    (tmp_path / "404.html").write_text("<html><head></head><body>Not Found</body></html>")
    return tmp_path


@pytest.fixture
def tmp_overlay(tmp_path: Path) -> Path:
    """Create a minimal overlay assets directory."""
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    (overlay / "ops.js").write_text("// overlay JS")
    (overlay / "ops.css").write_text("/* overlay CSS */")
    return overlay


@pytest.fixture
def config(tmp_site: Path, tmp_overlay: Path) -> Config:
    """Config pointing at test fixtures."""
    return Config(site_dir=tmp_site, overlay_dir=tmp_overlay)


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
