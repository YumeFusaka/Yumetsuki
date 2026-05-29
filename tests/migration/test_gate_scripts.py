from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
EMPTY_SHA256 = "sha256:" + hashlib.sha256(b"").hexdigest()


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        env=env,
    )


def test_test_inventory_gate_passes() -> None:
    completed = run_script("scripts/check_test_inventory.py")
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_pyside6_test_replacement_gate_passes() -> None:
    completed = run_script("scripts/check_pyside6_test_replacement.py")
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_replacement_status_phase5_gate_passes() -> None:
    completed = run_script("scripts/check_replacement_status.py", "--phase", "5", "--pre-delete")
    assert completed.returncode == 0, completed.stderr + completed.stdout


def test_replacement_status_phase5_pre_delete_rejects_manual_records(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    payload = json.loads(status.read_text(encoding="utf-8"))
    payload["items"][0]["phase_pass_records"] = [
        {
            "phase": 4,
            "command": "pnpm test",
            "date": "2026-05-29",
            "result_summary": "1 passed",
        },
        {
            "phase": 5,
            "command": "pnpm test",
            "date": "2026-05-29",
            "result_summary": "1 passed",
            "pre_delete": True,
        },
    ]
    status.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "5",
        "--pre-delete",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
    )

    assert completed.returncode == 1
    assert "缺少结构化 Phase 5 pre-delete 通过记录" in completed.stderr


def _write_minimal_inventory(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# 临时迁移清单",
                "",
                "| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |",
                "|---|---|---|---|---|---|---|---|",
                "| `tests/test_feedback_toast.py` | Qt toast | 删除 | Sakura Toast | `pnpm test` | Phase 1-4 | replacement status 记录连续两个阶段通过 | 恢复旧 toast 测试 |",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_minimal_status(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "legacy_test": "tests/test_feedback_toast.py",
                        "replacement_tests": [],
                        "replacement_commands": ["pnpm test"],
                        "retirement_action": "delete",
                        "phase_pass_records": [],
                        "delete_approved": False,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _run_report(command: str, generated_by: str = "scripts/run_migration_gate.py") -> dict:
    return {
        "schema_version": 1,
        "generated_by": generated_by,
        "phase": 1,
        "run_id": "pytest-fixture",
        "started_at": "2026-05-29T00:00:00Z",
        "finished_at": "2026-05-29T00:00:01Z",
        "schema_hash": "sha256:" + "a" * 64,
        "commands": [
            {
                "command": command,
                "command_hash": "sha256:" + hashlib.sha256(command.encode("utf-8")).hexdigest(),
                "cwd": ".",
                "started_at": "2026-05-29T00:00:00Z",
                "finished_at": "2026-05-29T00:00:01Z",
                "exit_code": 0,
                "result_summary": "1 passed",
                "stdout_sha256": EMPTY_SHA256,
                "stderr_sha256": EMPTY_SHA256,
            }
        ],
    }


def test_replacement_status_records_structured_run_report(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    report = tmp_path / "last_run_report.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    report.write_text(json.dumps(_run_report("pnpm test"), ensure_ascii=False), encoding="utf-8")

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "1",
        "--record-from-last-run",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
        "--run-report",
        str(report),
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(status.read_text(encoding="utf-8"))
    records = payload["items"][0]["phase_pass_records"]
    assert records[0]["command"] == "pnpm test"
    assert records[0]["command_hash"] == _run_report("pnpm test")["commands"][0]["command_hash"]
    assert records[0]["stdout_sha256"] == EMPTY_SHA256


def test_replacement_status_rejects_manual_run_report(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    report = tmp_path / "last_run_report.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    report.write_text(
        json.dumps(_run_report("pnpm test", generated_by="manual summary"), ensure_ascii=False),
        encoding="utf-8",
    )

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "1",
        "--record-from-last-run",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
        "--run-report",
        str(report),
    )

    assert completed.returncode == 1
    assert "generated_by 不得是 manual" in completed.stderr


def test_replacement_status_rejects_untrusted_run_report_generator(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    report = tmp_path / "last_run_report.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    report.write_text(
        json.dumps(_run_report("pnpm test", generated_by="local-notes.txt"), ensure_ascii=False),
        encoding="utf-8",
    )

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "1",
        "--record-from-last-run",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
        "--run-report",
        str(report),
    )

    assert completed.returncode == 1
    assert "generated_by 必须是可信生成器之一" in completed.stderr


def test_replacement_status_rejects_command_hash_mismatch(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    report = tmp_path / "last_run_report.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    payload = _run_report("pnpm test")
    payload["commands"][0]["command_hash"] = "sha256:" + "b" * 64
    report.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "1",
        "--record-from-last-run",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
        "--run-report",
        str(report),
    )

    assert completed.returncode == 1
    assert "command_hash 与 command 不匹配" in completed.stderr


def test_replacement_status_rejects_substring_command_match(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.md"
    status = tmp_path / "replacement_status.json"
    report = tmp_path / "last_run_report.json"
    _write_minimal_inventory(inventory)
    _write_minimal_status(status)
    report.write_text(json.dumps(_run_report("echo pnpm test"), ensure_ascii=False), encoding="utf-8")

    completed = run_script(
        "scripts/check_replacement_status.py",
        "--phase",
        "1",
        "--record-from-last-run",
        "--inventory",
        str(inventory),
        "--status",
        str(status),
        "--run-report",
        str(report),
    )

    assert completed.returncode == 1
    assert "last_run 没有匹配任何替换项" in completed.stderr


def test_run_migration_gate_writes_structured_report(tmp_path: Path) -> None:
    report = tmp_path / "last_run_report.json"
    command = "python -m pytest tests/rpc_contract/test_event_publisher.py -q"

    completed = run_script(
        "scripts/run_migration_gate.py",
        "--phase",
        "1",
        "--command",
        command,
        "--report",
        str(report),
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["generated_by"] == "scripts/run_migration_gate.py"
    assert payload["phase"] == 1
    assert payload["commands"][0]["command"] == command
    assert payload["commands"][0]["exit_code"] == 0
    assert payload["commands"][0]["command_hash"] == "sha256:" + hashlib.sha256(command.encode("utf-8")).hexdigest()


def test_run_migration_gate_rejects_unregistered_command(tmp_path: Path) -> None:
    report = tmp_path / "last_run_report.json"
    completed = run_script(
        "scripts/run_migration_gate.py",
        "--phase",
        "1",
        "--command",
        "python -m pytest tests/migration/test_gate_scripts.py -q",
        "--report",
        str(report),
    )

    assert completed.returncode == 1
    assert "命令未登记在替换表中" in completed.stderr
    assert not report.exists()


def test_run_migration_gate_rejects_collect_only_suffix(tmp_path: Path) -> None:
    report = tmp_path / "last_run_report.json"
    completed = run_script(
        "scripts/run_migration_gate.py",
        "--phase",
        "1",
        "--command",
        "python -m pytest tests/rpc_contract/test_event_publisher.py -q --collect-only",
        "--report",
        str(report),
    )

    assert completed.returncode == 1
    assert "命令未登记在替换表中" in completed.stderr
    assert not report.exists()
