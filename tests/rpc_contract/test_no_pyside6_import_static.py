from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_sidecar_static_scan_has_no_pyside6_or_qt() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_no_pyside6_in_sidecar.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
