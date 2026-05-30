from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_graph() -> list[dict[str, object]]:
    result = subprocess.run(
        [sys.executable, "scripts/trace_sidecar_import_graph.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)["modules"]


def test_sidecar_import_graph_excludes_qt_and_legacy_ui() -> None:
    graph = load_graph()
    modules = {str(item["module"]) for item in graph}
    files = {str(item["file"]).replace("\\", "/") for item in graph if item.get("file")}

    forbidden = ("PySide6", "QApplication", "QObject", "QThread", "Signal", "QtWebEngine")
    assert not any(any(token in module for token in forbidden) for module in modules)
    assert not any("/ui/" in file or file.endswith("/main.py") for file in files)
    assert not any(file.endswith("/core/ui_event_bridge.py") for file in files)


def test_legacy_qt_files_can_exist_without_being_sidecar_reachable() -> None:
    assert (ROOT / "ui").exists()
    assert (ROOT / "main.py").exists()
    assert (ROOT / "core" / "ui_event_bridge.py").exists()
    assert all("ui/" not in str(item.get("file", "")).replace("\\", "/") for item in load_graph())
