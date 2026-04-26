from __future__ import annotations

from pathlib import Path

from forge_overlay.static_handler import build_404, build_response, resolve_file


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

    def test_traversal_blocked_for_existing_file_outside_site(self, tmp_path: Path) -> None:
        site_dir = tmp_path / "site"
        site_dir.mkdir()
        (site_dir / "index.html").write_text("<html><head></head><body>OK</body></html>")

        secret = tmp_path / "secret.txt"
        secret.write_text("sensitive data")

        result = resolve_file(site_dir, "/../secret.txt")
        assert result is None

    def test_resolve_file_handles_oserror(self, tmp_site: Path, monkeypatch) -> None:
        original_resolve = Path.resolve

        def exploding_resolve(self: Path, strict: bool = False) -> Path:
            if "about" in str(self):
                raise OSError("simulated filesystem error")
            return original_resolve(self, strict=strict)

        monkeypatch.setattr(Path, "resolve", exploding_resolve)
        result = resolve_file(tmp_site, "/about")
        assert result is None


class TestBuildResponse:
    def test_build_response_css_mime_type(self, tmp_site: Path) -> None:
        result = resolve_file(tmp_site, "/style.css")
        assert result is not None

        resp = build_response(result)
        assert resp.media_type == "text/css"

    def test_build_response_unknown_extension(self, tmp_path: Path) -> None:
        unknown = tmp_path / "data.unknownext"
        unknown.write_text("stuff")

        resp = build_response(unknown)
        assert resp.media_type == "text/plain"


class TestBuild404:
    def test_custom_404(self, tmp_site: Path) -> None:
        resp = build_404(tmp_site)
        assert resp.status_code == 404

    def test_default_404(self, tmp_path: Path) -> None:
        resp = build_404(tmp_path)
        assert resp.status_code == 404
