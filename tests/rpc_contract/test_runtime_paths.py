from __future__ import annotations

import os
from pathlib import Path

import pytest

from python_core.runtime_paths import RuntimePaths, assert_default_resource_copy, assert_in_scope


def runtime_payload(root: Path, mode: str = "dev", models_dir: Path | None = None) -> dict[str, object]:
    app_data = root / "data"
    return {
        "mode": mode,
        "app_data_dir": str(app_data),
        "config_dir": str(app_data / "config"),
        "log_dir": str(app_data / "logs"),
        "memory_dir": str(app_data / "memory"),
        "vision_dir": str(app_data / "vision"),
        "browser_sessions_dir": str(app_data / "browser_sessions"),
        "temp_dir": str(app_data / "temp"),
        "resource_dir": str(root / "resources"),
        "models_dir": str(models_dir or app_data / "models"),
        "platform": "windows",
        "repo_root": str(root),
    }


def test_windows_dev_mode_allows_explicit_repo_local_data(tmp_path: Path) -> None:
    paths = RuntimePaths.from_json(runtime_payload(tmp_path), mode="dev")
    assert paths.config_dir == (tmp_path / "data" / "config").resolve()


def test_release_mode_rejects_repo_local_runtime_dirs(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="release 模式运行期路径不得位于仓库内"):
        RuntimePaths.from_json(runtime_payload(tmp_path, mode="release"), mode="release")


def test_runtime_dirs_are_resolved_before_use(tmp_path: Path) -> None:
    payload = runtime_payload(tmp_path)
    payload["config_dir"] = str(tmp_path / "data" / "config" / ".." / "config")

    paths = RuntimePaths.from_json(payload, mode="dev")

    for value in [
        paths.config_dir,
        paths.log_dir,
        paths.memory_dir,
        paths.vision_dir,
        paths.browser_sessions_dir,
        paths.temp_dir,
        paths.resource_dir,
        paths.models_dir,
    ]:
        assert value.is_absolute()
        assert ".." not in value.parts


def test_runtime_paths_reject_parent_traversal_escape(tmp_path: Path) -> None:
    payload = runtime_payload(tmp_path)
    payload["config_dir"] = str(tmp_path / "data" / ".." / "escaped_config")

    with pytest.raises(ValueError, match="config_dir 不在允许范围内"):
        RuntimePaths.from_json(payload, mode="dev")


@pytest.mark.skipif(os.name != "nt", reason="UNC escape is Windows-specific")
def test_runtime_paths_reject_unc_escape(tmp_path: Path) -> None:
    payload = runtime_payload(tmp_path)
    payload["config_dir"] = r"\\server\share\config"

    with pytest.raises(ValueError, match="UNC 路径不允许"):
        RuntimePaths.from_json(payload, mode="dev")


def test_runtime_paths_reject_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "data" / "linked_config"
    link.parent.mkdir()
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"当前文件系统不允许创建目录符号链接：{exc}")
    payload = runtime_payload(tmp_path)
    payload["config_dir"] = str(link)

    with pytest.raises(ValueError, match="config_dir 不在允许范围内"):
        RuntimePaths.from_json(payload, mode="dev")


def test_external_models_dir_requires_tauri_scope(tmp_path: Path) -> None:
    external_models = tmp_path / "external" / "models"
    payload = runtime_payload(tmp_path, models_dir=external_models)

    with pytest.raises(ValueError, match="models_dir 不在 Tauri 授权范围内"):
        RuntimePaths.from_json(payload, mode="dev")

    paths = RuntimePaths.from_json(payload, mode="dev", model_scope_roots=[tmp_path / "external"])
    assert paths.models_dir == external_models.resolve()


def test_assert_in_scope_resolves_before_comparing(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    target = allowed / "child" / ".." / "child"
    assert assert_in_scope(target, [allowed]) == target.resolve()


def test_default_resources_copy_to_app_data_only(tmp_path: Path) -> None:
    paths = RuntimePaths.from_json(runtime_payload(tmp_path), mode="dev")
    source = paths.resource_dir / "defaults" / "config.json"
    good_destination = paths.app_data_dir / "config" / "config.json"
    bad_destination = paths.resource_dir / "defaults" / "config.json"

    assert_default_resource_copy(paths, source, good_destination)
    with pytest.raises(ValueError, match="默认资源不得原地写入"):
        assert_default_resource_copy(paths, source, bad_destination)
