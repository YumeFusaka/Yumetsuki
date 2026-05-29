from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_docs_no_stale_ui_status.py"


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def test_default_phase5_docs_state_passes() -> None:
    result = run_script()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 5 文档 stale 扫描通过" in result.stdout


def test_phase5_scan_rejects_phase01_status_fixture(tmp_path: Path) -> None:
    stale_doc = tmp_path / "stale.md"
    stale_doc.write_text(
        "当前 Tauri UI 迁移实施已开始，处于 Phase 0/1。旧 PySide6 UI 仍保留为双跑参考。\n",
        encoding="utf-8",
    )

    result = run_script("--phase", "5", "--path", str(stale_doc))
    assert result.returncode == 1
    assert "phase01_state" in result.stderr


def test_phase5_scan_rejects_deleted_legacy_entry_fixtures(tmp_path: Path) -> None:
    stale_doc = tmp_path / "legacy.md"
    stale_doc.write_text(
        "\n".join(
            [
                "历史 PySide6 入口仍在仓库中，等待用户确认删除范围后再移除。",
                "Legacy PySide6 当前仍可运行：python main.py",
                "Tauri 迁移工程在 Phase 1 目录建立后使用。",
                "设置中心所有 QComboBox 必须复用 ui/theme.py。",
            ]
        ),
        encoding="utf-8",
    )

    result = run_script("--phase", "5", "--path", str(stale_doc))
    assert result.returncode == 1
    assert "pending_delete_confirmation" in result.stderr
    assert "legacy_pyside6_runnable" in result.stderr
    assert "legacy_main_entry" in result.stderr
    assert "phase1_directory_pending" in result.stderr
    assert "qt_control_reference" in result.stderr
    assert "legacy_ui_path_reference" in result.stderr


def test_phase01_scan_still_supports_archive_state_fixture(tmp_path: Path) -> None:
    phase01_doc = tmp_path / "phase01.md"
    phase01_doc.write_text(
        "Phase 0/1：PySide6 legacy 双跑参考，Tauri 新主线目标。\n",
        encoding="utf-8",
    )

    result = run_script("--phase", "1", "--path", str(phase01_doc))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Phase 0/1 文档状态扫描通过" in result.stdout
