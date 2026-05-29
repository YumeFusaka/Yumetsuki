from __future__ import annotations

from pathlib import Path

import pytest

from python_core.runtime_paths import RuntimePathError, RuntimePaths


def payload(base: Path) -> dict[str, str]:
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


def test_runtime_paths_schema_rejects_missing_and_unknown_fields(tmp_path: Path) -> None:
    data = payload(tmp_path)
    data.pop("log_dir")
    with pytest.raises(RuntimePathError):
        RuntimePaths.from_json(data)

    data = payload(tmp_path)
    data["extra"] = "unexpected"
    with pytest.raises(RuntimePathError):
        RuntimePaths.from_json(data)


def test_runtime_paths_json_round_trip(tmp_path: Path) -> None:
    paths = RuntimePaths.from_json(payload(tmp_path))
    round_trip = RuntimePaths.from_json(paths.to_json())
    assert round_trip == paths
