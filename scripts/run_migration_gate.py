from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from check_replacement_status import command_hash, command_matches_target, parse_replacement_table
except ImportError:
    from scripts.check_replacement_status import command_hash, command_matches_target, parse_replacement_table


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "tests" / "migration" / "last_run_report.json"
GENERATOR_ID = "scripts/run_migration_gate.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def schema_hash() -> str:
    catalog = ROOT / "python_core" / "rpc" / "schema" / "catalog.json"
    if catalog.is_file():
        return "sha256:" + hashlib.sha256(catalog.read_bytes()).hexdigest()
    return "sha256:" + "0" * 64


def command_cwd(command: str) -> Path:
    if command.startswith("pnpm "):
        return ROOT
    if command.startswith("cargo "):
        return ROOT / "apps" / "desktop" / "src-tauri"
    return ROOT


def command_args(command: str) -> list[str]:
    parts = shlex.split(command, posix=False)
    if parts and parts[0] == "python":
        parts[0] = sys.executable
    elif parts and os.name == "nt":
        resolved = shutil.which(parts[0]) or shutil.which(f"{parts[0]}.cmd") or shutil.which(f"{parts[0]}.exe")
        if resolved:
            parts[0] = resolved
    return parts


def allowed_commands() -> set[str]:
    commands: set[str] = set()
    for row in parse_replacement_table().values():
        for target in row.targets:
            normalized = " ".join(target.split())
            if normalized.startswith(("python ", "pnpm ", "cargo ")):
                commands.add(normalized)
    return commands


def assert_allowed(command: str, allowed: set[str]) -> None:
    if not any(command_matches_target(command, target) for target in allowed):
        allowed_preview = "\n".join(f"  - {item}" for item in sorted(allowed))
        raise SystemExit(f"命令未登记在替换表中，拒绝生成 run report：{command}\n允许命令：\n{allowed_preview}")


def run_command(command: str) -> dict:
    cwd = command_cwd(command)
    started_at = utc_now()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        command_args(command),
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    finished_at = utc_now()
    summary_lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
    result_summary = summary_lines[-1] if summary_lines else f"exit_code={completed.returncode}"
    return {
        "command": command,
        "command_hash": command_hash(command),
        "cwd": str(cwd.relative_to(ROOT)).replace("\\", "/") or ".",
        "started_at": started_at,
        "finished_at": finished_at,
        "exit_code": completed.returncode,
        "result_summary": result_summary,
        "stdout_sha256": sha256_text(completed.stdout),
        "stderr_sha256": sha256_text(completed.stderr),
    }


def write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行已登记的迁移替代 gate，并生成结构化 run report。")
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument("--command", dest="commands", action="append", required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    normalized_commands = [" ".join(command.split()) for command in args.commands]
    allowed = allowed_commands()
    for command in normalized_commands:
        assert_allowed(command, allowed)

    started_at = utc_now()
    command_records = [run_command(command) for command in normalized_commands]
    finished_at = utc_now()
    payload = {
        "schema_version": 1,
        "generated_by": GENERATOR_ID,
        "phase": args.phase,
        "run_id": sha256_text(started_at + "\n" + "\n".join(normalized_commands)),
        "started_at": started_at,
        "finished_at": finished_at,
        "schema_hash": schema_hash(),
        "commands": command_records,
    }
    report_path = args.report
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    write_report(report_path, payload)

    failed = [record for record in command_records if record["exit_code"] != 0]
    if failed:
        for record in failed:
            print(f"迁移 gate 命令失败：{record['command']} -> {record['exit_code']}", file=sys.stderr)
        return 1

    print(f"迁移 gate run report 已生成：{report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
