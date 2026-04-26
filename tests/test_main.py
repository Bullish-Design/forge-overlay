from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

import forge_overlay.main as main_mod
from forge_overlay.config import Config

RUNNER = CliRunner()


def _patch_runtime(monkeypatch: object) -> tuple[dict[str, object], MagicMock]:
    captured: dict[str, object] = {}
    uvicorn_run = MagicMock()

    def fake_create_app(config: Config) -> str:
        captured["config"] = config
        return "fake-asgi-app"

    monkeypatch.setattr(main_mod, "create_app", fake_create_app)
    monkeypatch.setattr(main_mod, "uvicorn", MagicMock(run=uvicorn_run))
    return captured, uvicorn_run


def test_defaults_with_no_args_or_env(monkeypatch) -> None:
    captured, _uvicorn_run = _patch_runtime(monkeypatch)

    result = RUNNER.invoke(main_mod.app, [])

    assert result.exit_code == 0
    config = captured["config"]
    assert isinstance(config, Config)
    assert config.site_dir == Path("public")
    assert config.overlay_dir == Path("overlay")
    assert config.api_upstream == "http://127.0.0.1:3000"
    assert config.host == "127.0.0.1"
    assert config.port == 8080


def test_env_vars_override_defaults(monkeypatch) -> None:
    captured, _uvicorn_run = _patch_runtime(monkeypatch)
    env = {
        "FORGE_SITE_DIR": "/tmp/demo-site",
        "FORGE_OVERLAY_DIR": "/tmp/demo-overlay",
        "FORGE_API_UPSTREAM": "http://localhost:9999",
        "FORGE_HOST": "0.0.0.0",
        "FORGE_PORT": "9090",
    }

    result = RUNNER.invoke(main_mod.app, [], env=env)

    assert result.exit_code == 0
    config = captured["config"]
    assert isinstance(config, Config)
    assert config.site_dir == Path("/tmp/demo-site")
    assert config.overlay_dir == Path("/tmp/demo-overlay")
    assert config.api_upstream == "http://localhost:9999"
    assert config.host == "0.0.0.0"
    assert config.port == 9090


def test_cli_flags_override_env_vars(monkeypatch) -> None:
    captured, _uvicorn_run = _patch_runtime(monkeypatch)
    env = {
        "FORGE_SITE_DIR": "/tmp/from-env-site",
        "FORGE_OVERLAY_DIR": "/tmp/from-env-overlay",
        "FORGE_API_UPSTREAM": "http://localhost:8088",
        "FORGE_HOST": "0.0.0.0",
        "FORGE_PORT": "9090",
    }

    result = RUNNER.invoke(
        main_mod.app,
        [
            "--site-dir",
            "/tmp/from-cli-site",
            "--overlay-dir",
            "/tmp/from-cli-overlay",
            "--api-upstream",
            "http://localhost:7071",
            "--host",
            "127.0.0.2",
            "--port",
            "7070",
        ],
        env=env,
    )

    assert result.exit_code == 0
    config = captured["config"]
    assert isinstance(config, Config)
    assert config.site_dir == Path("/tmp/from-cli-site")
    assert config.overlay_dir == Path("/tmp/from-cli-overlay")
    assert config.api_upstream == "http://localhost:7071"
    assert config.host == "127.0.0.2"
    assert config.port == 7070


def test_invalid_port_exits_nonzero() -> None:
    result = RUNNER.invoke(main_mod.app, ["--port", "abc"])

    assert result.exit_code != 0
    assert "Invalid value for '--port'" in result.output


def test_uvicorn_receives_config_values(monkeypatch) -> None:
    captured, uvicorn_run = _patch_runtime(monkeypatch)

    result = RUNNER.invoke(
        main_mod.app,
        ["--host", "0.0.0.0", "--port", "8191", "--site-dir", "public", "--overlay-dir", "overlay"],
    )

    assert result.exit_code == 0
    config = captured["config"]
    assert isinstance(config, Config)
    uvicorn_run.assert_called_once_with(
        "fake-asgi-app",
        host="0.0.0.0",
        port=8191,
        log_level="info",
    )


def test_main_calls_typer_app(monkeypatch) -> None:
    app_call = MagicMock()
    monkeypatch.setattr(main_mod, "app", app_call)

    main_mod.main()

    app_call.assert_called_once_with()
