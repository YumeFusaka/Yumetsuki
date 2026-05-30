from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_sidecar_graph_has_no_static_or_dynamic_pyside6_loads() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/trace_sidecar_import_graph.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    graph = json.loads(result.stdout)["modules"]
    suspect_tokens = ["from PySide6", "import PySide6", "import_module(\"PySide6", "__import__(\"PySide6", "QtWebEngine", "PySide6"]
    for item in graph:
        if not item.get("is_project"):
            continue
        file_name = item.get("file")
        if not file_name:
            continue
        source = Path(str(file_name)).read_text(encoding="utf-8")
        assert not any(token in source for token in suspect_tokens), file_name


def test_trace_script_reports_no_legacy_ui_import_chain() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/trace_sidecar_import_graph.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ui." not in result.stderr
    assert result.returncode == 0
