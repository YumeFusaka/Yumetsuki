from __future__ import annotations

from pathlib import Path

import pytest

from python_core.runtime_paths import RuntimePathError, RuntimePaths, assert_in_scope


def make_payload(base: Path) -> dict[str, str]:
    return {
        "app_data_dir": str(base),
        "config_dir": str(base / "config"),
        "log_dir": str(base / "logs"),
        "memory_dir": str(base / "memory"),
        "vision_dir": str(base / "vision"),
        "browser_sessions_dir": str(base / "browser_sessions"),
        "temp_dir": str(base / "temp"),
        "resource_dir": str(base / "resources"),
        "models_dir": str(base / "models"),
        "platform": "windows",
    }


def test_runtime_paths_resolve_and_scope_app_data(tmp_path: Path) -> None:
    paths = RuntimePaths.from_json(make_payload(tmp_path), mode="dev")
    assert paths.config_dir.is_absolute()
    assert paths.config_dir == (tmp_path / "config").resolve()
    assert paths.models_dir == (tmp_path / "models").resolve()


def test_release_mode_rejects_repo_local_runtime_dirs(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    payload = make_payload(repo / "data")
    with pytest.raises(RuntimePathError):
        RuntimePaths.from_json(payload, mode="release", repo_root=repo)


def test_rejects_relative_and_out_of_scope_paths(tmp_path: Path) -> None:
    payload = make_payload(tmp_path)
    payload["config_dir"] = "relative/config"
    with pytest.raises(RuntimePathError):
        RuntimePaths.from_json(payload, mode="dev")

    with pytest.raises(RuntimePathError):
        assert_in_scope(tmp_path.parent / "escape", [tmp_path / "allowed"])


def test_external_models_require_explicit_scope(tmp_path: Path) -> None:
    payload = make_payload(tmp_path / "app")
    external = tmp_path / "external-models"
    payload["models_dir"] = str(external)
    with pytest.raises(RuntimePathError):
        RuntimePaths.from_json(payload, mode="dev")
    scoped = RuntimePaths.from_json(payload, mode="dev", allowed_model_roots=[external])
    assert scoped.models_dir == external.resolve()
