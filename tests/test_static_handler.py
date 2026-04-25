from __future__ import annotations

from pathlib import Path

from forge_overlay.static_handler import build_404, resolve_file


class TestResolveFile:
    def test_root_resolves_to_index(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/")
        assert result is not None
        assert result.name == "index.html"

    def test_exact_file(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/style.css")
        assert result is not None
        assert result.name == "style.css"

    def test_clean_url_html_extension(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/about")
        assert result is not None
        assert result.name == "about.html"

    def test_directory_index(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/blog")
        assert result is not None
        assert result.name == "index.html"
        assert "blog" in str(result)

    def test_missing_file_returns_none(self, tmp_site: Path) -> None:
        assert resolve_file(tmp_site, "/nonexistent") is None

    def test_path_traversal_blocked(self, tmp_site: Path) -> None:
        assert resolve_file(tmp_site, "/../../../etc/passwd") is None


class TestBuild404:
    def test_custom_404(self, tmp_site: Path) -> None:
        resp = build_404(tmp_site)
        assert resp.status_code == 404

    def test_default_404(self, tmp_path: Path) -> None:
        resp = build_404(tmp_path)
        assert resp.status_code == 404
