from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_sidecar_stdout_static_scan_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/check_no_stdout_in_sidecar.py"],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
