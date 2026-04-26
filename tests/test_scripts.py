from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import forge_overlay._scripts as scripts_mod


def test_repo_root_finds_pyproject() -> None:
    root = scripts_mod._repo_root()
    assert (root / "pyproject.toml").is_file()


def test_repo_root_raises_when_pyproject_missing(monkeypatch) -> None:
    class FakePath:
        def resolve(self) -> FakePath:
            return self

        @property
        def parent(self) -> FakePath:
            return self

        @property
        def parents(self) -> tuple[FakePath, ...]:
            return ()

        def __truediv__(self, _part: str) -> FakePath:
            return self

        def is_file(self) -> bool:
            return False

    monkeypatch.setattr(scripts_mod, "Path", MagicMock(__file__=FakePath(), return_value=FakePath()))

    with pytest.raises(RuntimeError, match="Cannot find repo root"):
        scripts_mod._repo_root()


def test_run_script_without_extra_args(monkeypatch) -> None:
    monkeypatch.setattr(scripts_mod, "_repo_root", lambda: Path("/repo"))
    call_mock = MagicMock(return_value=0)
    monkeypatch.setattr(scripts_mod.subprocess, "call", call_mock)

    with pytest.raises(SystemExit) as exc:
        scripts_mod._run_script("generate-demo.sh")

    assert exc.value.code == 0
    call_mock.assert_called_once_with(["bash", "/repo/demo/scripts/generate-demo.sh"])


def test_run_script_with_extra_args(monkeypatch) -> None:
    monkeypatch.setattr(scripts_mod, "_repo_root", lambda: Path("/repo"))
    call_mock = MagicMock(return_value=0)
    monkeypatch.setattr(scripts_mod.subprocess, "call", call_mock)
    monkeypatch.setattr(scripts_mod.sys, "argv", ["forge-demo", "--port", "9090"])

    with pytest.raises(SystemExit) as exc:
        scripts_mod._run_script("run-demo.sh", extra_args=True)

    assert exc.value.code == 0
    call_mock.assert_called_once_with(["bash", "/repo/demo/scripts/run-demo.sh", "--port", "9090"])


def test_run_demo_delegates(monkeypatch) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(scripts_mod, "_run_script", run_mock)

    scripts_mod.run_demo()

    run_mock.assert_called_once_with("run-demo.sh", extra_args=True)


def test_generate_demo_delegates(monkeypatch) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(scripts_mod, "_run_script", run_mock)

    scripts_mod.generate_demo()

    run_mock.assert_called_once_with("generate-demo.sh")


def test_clean_demo_delegates(monkeypatch) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(scripts_mod, "_run_script", run_mock)

    scripts_mod.clean_demo()

    run_mock.assert_called_once_with("clean-demo.sh")
