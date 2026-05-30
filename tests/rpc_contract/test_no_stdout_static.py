from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_sidecar_import_graph_has_no_stdout_pollution_points() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_no_stdout_in_sidecar.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_stdout_scan_scope_ignores_unreachable_legacy_ui() -> None:
    assert (ROOT / "ui" / "chat" / "window.py").exists()
    result = subprocess.run(
        [sys.executable, "scripts/check_no_stdout_in_sidecar.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ui/chat/window.py" not in (result.stdout + result.stderr).replace("\\", "/")
