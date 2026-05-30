from __future__ import annotations

import json
from pathlib import Path

import pytest

from python_core.runtime_paths import RuntimePaths


FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "runtime_paths"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_windows_dev_runtime_paths_fixture_is_valid() -> None:
    paths = RuntimePaths.from_json(load_fixture("windows_dev.json"))
    assert paths.mode == "dev"


def test_windows_release_runtime_paths_fixture_is_valid() -> None:
    paths = RuntimePaths.from_json(load_fixture("windows_release.json"))
    assert paths.mode == "release"


def test_runtime_paths_reject_missing_fields() -> None:
    data = load_fixture("windows_dev.json")
    data.pop("logs_root")
    with pytest.raises(ValueError, match="缺少字段"):
        RuntimePaths.from_json(data)


def test_runtime_paths_reject_extra_fields() -> None:
    data = load_fixture("windows_dev.json")
    data["project_data_root"] = "E:/Project/Yumetsuki/data"
    with pytest.raises(ValueError, match="未知字段"):
        RuntimePaths.from_json(data)


def test_release_runtime_paths_reject_repo_data() -> None:
    with pytest.raises(ValueError, match="release 模式运行期路径不得位于仓库内"):
        RuntimePaths.from_json(load_fixture("invalid_repo_release.json"))
