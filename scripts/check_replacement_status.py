from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "tests" / "migration" / "test_inventory.md"
STATUS_PATH = ROOT / "tests" / "migration" / "replacement_status.json"
RUN_REPORT_PATH = ROOT / "tests" / "migration" / "last_run_report.json"
TABLE_HEADER = "| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |"
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
TRUSTED_RUN_REPORT_GENERATORS = {
    "scripts/run_migration_gate.py",
    "scripts/run_phase_gate.py",
    "pytest",
    "vitest",
    "playwright",
    "cargo",
}


@dataclass(frozen=True)
class ReplacementRow:
    legacy_test: str
    action: str
    targets: tuple[str, ...]
    phase: str


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def normalize_action(value: str) -> str:
    mapping = {
        "删除": "delete",
        "同名改写": "rewrite_same_name",
        "delete": "delete",
        "rewrite_same_name": "rewrite_same_name",
    }
    return mapping.get(value, value)


def extract_backtick_values(value: str) -> list[str]:
    return [normalize_path(match) for match in re.findall(r"`([^`]+)`", value)]


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_replacement_table() -> dict[str, ReplacementRow]:
    if not INVENTORY_PATH.exists():
        raise SystemExit(f"缺少迁移清单：{display_path(INVENTORY_PATH)}")
    rows: dict[str, ReplacementRow] = {}
    in_table = False
    for line in INVENTORY_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() == TABLE_HEADER:
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("|---"):
            continue
        if not line.startswith("|"):
            break
        cells = split_markdown_row(line)
        if len(cells) != 8:
            raise SystemExit(f"替换表列数异常：{line}")
        legacy_values = extract_backtick_values(cells[0])
        if len(legacy_values) != 1:
            raise SystemExit(f"替换表旧测试列必须有且只有一个路径：{line}")
        legacy = legacy_values[0]
        if legacy in rows:
            raise SystemExit(f"替换表旧测试重复：{legacy}")
        rows[legacy] = ReplacementRow(
            legacy_test=legacy,
            action=normalize_action(cells[2]),
            targets=tuple(extract_backtick_values(cells[4])),
            phase=cells[5],
        )
    if not rows:
        raise SystemExit("未找到 PySide6 绑定测试替换表")
    return rows


def load_status() -> dict[str, Any]:
    if not STATUS_PATH.exists():
        raise SystemExit(f"缺少替换状态文件：{display_path(STATUS_PATH)}")
    try:
        data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"替换状态 JSON 解析失败：{exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise SystemExit("replacement_status.json 必须包含 items 数组")
    return data


def save_status(data: dict[str, Any]) -> None:
    STATUS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def command_hash(command: str) -> str:
    return "sha256:" + hashlib.sha256(command.encode("utf-8")).hexdigest()


def command_matches_target(command: str, target: str) -> bool:
    command = " ".join(command.strip().split())
    target = " ".join(target.strip().split())
    if not command or not target:
        return False
    return command == target


def require_sha256(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not HASH_RE.match(value):
        errors.append(f"{field} 必须是 sha256:<64 hex>")


def load_run_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"--record-from-last-run 需要结构化 run report：{display_path(path)}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"run report JSON 解析失败：{exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("run report 根对象必须是 object")
    return payload


def validate_run_report(report: dict[str, Any], phase: int) -> list[str]:
    errors: list[str] = []
    if report.get("schema_version") != 1:
        errors.append("run_report.schema_version 必须等于 1")
    if report.get("phase") != phase:
        errors.append(f"run_report.phase 必须等于当前 --phase {phase}")
    generated_by = report.get("generated_by")
    if not isinstance(generated_by, str) or not generated_by.strip():
        errors.append("run_report.generated_by 必须是非空字符串")
    elif "manual" in generated_by.lower():
        errors.append("run_report.generated_by 不得是 manual")
    elif generated_by not in TRUSTED_RUN_REPORT_GENERATORS:
        errors.append(
            "run_report.generated_by 必须是可信生成器之一: "
            + ", ".join(sorted(TRUSTED_RUN_REPORT_GENERATORS))
        )
    for field in ("run_id", "started_at", "finished_at"):
        if not isinstance(report.get(field), str) or not report[field].strip():
            errors.append(f"run_report.{field} 必须是非空字符串")
    schema_hash = report.get("schema_hash")
    if schema_hash is not None:
        require_sha256(schema_hash, "run_report.schema_hash", errors)

    commands = report.get("commands")
    if not isinstance(commands, list) or not commands:
        errors.append("run_report.commands 必须是非空数组")
        return errors

    for index, command_record in enumerate(commands):
        prefix = f"run_report.commands[{index}]"
        if not isinstance(command_record, dict):
            errors.append(f"{prefix} 必须是 object")
            continue
        command = command_record.get("command")
        if not isinstance(command, str) or not command.strip():
            errors.append(f"{prefix}.command 必须是非空字符串")
            continue
        expected_hash = command_hash(command.strip())
        if command_record.get("command_hash") != expected_hash:
            errors.append(f"{prefix}.command_hash 与 command 不匹配")
        if command_record.get("exit_code") != 0:
            errors.append(f"{prefix}.exit_code 必须等于 0")
        for field in ("cwd", "started_at", "finished_at", "result_summary"):
            if not isinstance(command_record.get(field), str) or not command_record[field].strip():
                errors.append(f"{prefix}.{field} 必须是非空字符串")
        require_sha256(command_record.get("stdout_sha256"), f"{prefix}.stdout_sha256", errors)
        require_sha256(command_record.get("stderr_sha256"), f"{prefix}.stderr_sha256", errors)
    return errors


def validate_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["phase_pass_records 中的记录必须是对象"]
    if not isinstance(record.get("phase"), int):
        errors.append("记录缺少整数 phase")
    if not isinstance(record.get("command"), str) or not record["command"].strip():
        errors.append("记录缺少 command")
    if not isinstance(record.get("date"), str) or not record["date"].strip():
        errors.append("记录缺少 date")
    if not isinstance(record.get("result_summary"), str) or not record["result_summary"].strip():
        errors.append("记录缺少 result_summary")
    return errors


def structured_record_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    run_id = record.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        errors.append("结构化记录缺少 run_id")
    if record.get("exit_code") != 0:
        errors.append("结构化记录 exit_code 必须等于 0")
    require_sha256(record.get("command_hash"), "结构化记录 command_hash", errors)
    require_sha256(record.get("stdout_sha256"), "结构化记录 stdout_sha256", errors)
    require_sha256(record.get("stderr_sha256"), "结构化记录 stderr_sha256", errors)
    if "schema_hash" in record:
        require_sha256(record.get("schema_hash"), "结构化记录 schema_hash", errors)
    return errors


def has_structured_record_fields(record: dict[str, Any]) -> bool:
    return any(
        field in record
        for field in ("run_id", "exit_code", "command_hash", "stdout_sha256", "stderr_sha256")
    )


def has_consecutive_phase_records(records: list[dict[str, Any]]) -> bool:
    phases = sorted({record["phase"] for record in records if isinstance(record.get("phase"), int)})
    return any(next_phase == phase + 1 for phase, next_phase in zip(phases, phases[1:]))


def has_phase5_pre_delete_record(records: list[dict[str, Any]]) -> bool:
    return any(record.get("phase") == 5 and record.get("pre_delete") is True for record in records)


def has_structured_phase5_pre_delete_record(records: list[dict[str, Any]]) -> bool:
    return any(
        record.get("phase") == 5
        and record.get("pre_delete") is True
        and has_structured_record_fields(record)
        and not structured_record_errors(record)
        for record in records
    )


def status_targets(item: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in ("replacement_tests", "replacement_commands"):
        field_value = item.get(field, [])
        if isinstance(field_value, list):
            values.update(str(value).replace("\\", "/") for value in field_value)
    return values


def validate_items(
    data: dict[str, Any],
    table: dict[str, ReplacementRow],
    phase: int,
    pre_delete: bool,
    enforce_phase_gate: bool = True,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    errors: list[str] = []
    status_items: dict[str, dict[str, Any]] = {}

    for item in data["items"]:
        if not isinstance(item, dict):
            errors.append("items 中的条目必须是对象")
            continue
        legacy = item.get("legacy_test")
        if not isinstance(legacy, str) or not legacy:
            errors.append("状态条目缺少 legacy_test")
            continue
        legacy = normalize_path(legacy)
        if legacy in status_items:
            errors.append(f"replacement_status.json 中 legacy_test 重复：{legacy}")
            continue
        status_items[legacy] = item

        row = table.get(legacy)
        if row is None:
            errors.append(f"replacement_status.json 包含替换表之外的条目：{legacy}")
            continue
        if normalize_action(str(item.get("retirement_action"))) != row.action:
            errors.append(f"{legacy} 的 retirement_action 与替换表不一致")
        if not isinstance(item.get("replacement_tests"), list):
            errors.append(f"{legacy} 的 replacement_tests 必须是数组")
        if not isinstance(item.get("phase_pass_records"), list):
            errors.append(f"{legacy} 的 phase_pass_records 必须是数组")
            continue
        if not isinstance(item.get("delete_approved"), bool):
            errors.append(f"{legacy} 的 delete_approved 必须是布尔值")

        covered_targets = status_targets(item)
        table_targets = set(row.targets)
        missing_targets = table_targets - covered_targets
        if missing_targets:
            errors.append(f"{legacy} 的状态文件未覆盖替换表目标：{', '.join(sorted(missing_targets))}")

        records = item["phase_pass_records"]
        for index, record in enumerate(records):
            for record_error in validate_record(record):
                errors.append(f"{legacy} 第 {index + 1} 条通过记录无效：{record_error}")
            if isinstance(record, dict) and has_structured_record_fields(record):
                for record_error in structured_record_errors(record):
                    errors.append(f"{legacy} 第 {index + 1} 条通过记录无效：{record_error}")

        valid_records = [record for record in records if isinstance(record, dict)]
        if enforce_phase_gate:
            if phase < 5 and item.get("delete_approved") is True:
                errors.append(f"{legacy} 在 Phase {phase} 不允许提前 delete_approved=true")
            if item.get("delete_approved") is True:
                approval = item.get("approval_record")
                if not isinstance(approval, dict) or not approval.get("date") or not approval.get("scope_summary"):
                    errors.append(f"{legacy} delete_approved=true 时必须有 approval_record.date 和 scope_summary")
                if not has_consecutive_phase_records(valid_records):
                    errors.append(f"{legacy} delete_approved=true 但缺少连续两个阶段通过记录")

            if phase >= 5 or pre_delete:
                if not has_consecutive_phase_records(valid_records):
                    errors.append(f"{legacy} 缺少连续两个阶段通过记录")
                if pre_delete and phase >= 5 and not has_phase5_pre_delete_record(valid_records):
                    errors.append(f"{legacy} 缺少 Phase 5 pre-delete 通过记录")
                if pre_delete and phase >= 5 and not has_structured_phase5_pre_delete_record(valid_records):
                    errors.append(f"{legacy} 缺少结构化 Phase 5 pre-delete 通过记录")
                legacy_exists = (ROOT / legacy).exists()
                if phase >= 5 and not legacy_exists and item.get("delete_approved") is not True:
                    errors.append(f"{legacy} 已不存在，但 delete_approved=false")

    missing_status = set(table) - set(status_items)
    if missing_status:
        errors.append("replacement_status.json 缺少替换表条目：\n" + "\n".join(f"  - {path}" for path in sorted(missing_status)))

    return errors, status_items


def match_last_run_to_items(
    data: dict[str, Any],
    status_items: dict[str, dict[str, Any]],
    phase: int,
    pre_delete: bool,
    run_report_path: Path,
) -> list[str]:
    if "last_run" in data:
        return ["replacement_status.json 顶层 last_run 已废弃；请使用结构化 run report 文件并通过 --run-report 指定"]
    run_report = load_run_report(run_report_path)
    errors = validate_run_report(run_report, phase)
    if errors:
        return errors

    commands = run_report["commands"]
    run_date = str(run_report.get("finished_at") or datetime.now().date().isoformat())
    schema_hash = str(run_report.get("schema_hash") or "")
    run_id = str(run_report.get("run_id") or "")
    errors: list[str] = []
    changed = False

    for command_record in commands:
        command = str(command_record["command"]).strip()
        result_summary = str(command_record["result_summary"]).strip()
        for item in status_items.values():
            targets = status_targets(item)
            if not any(command_matches_target(command, target) for target in targets):
                continue
            record = {
                "phase": phase,
                "command": command,
                "date": run_date,
                "result_summary": result_summary,
                "exit_code": 0,
                "command_hash": command_record["command_hash"],
                "stdout_sha256": command_record["stdout_sha256"],
                "stderr_sha256": command_record["stderr_sha256"],
            }
            if schema_hash:
                record["schema_hash"] = schema_hash
            if run_id:
                record["run_id"] = run_id
            if pre_delete:
                record["pre_delete"] = True
            existing = item.setdefault("phase_pass_records", [])
            if record not in existing:
                existing.append(record)
                changed = True

    if changed:
        save_status(data)
    else:
        errors.append("last_run 没有匹配任何替换项，未记录新通过结果")
    return errors


def main() -> int:
    global INVENTORY_PATH, STATUS_PATH

    parser = argparse.ArgumentParser(description="检查 PySide6 绑定测试替换状态。")
    parser.add_argument("--phase", type=int, default=0, help="迁移阶段。")
    parser.add_argument("--pre-delete", action="store_true", help="执行 Phase 5 删除前 gate。")
    parser.add_argument("--record-from-last-run", action="store_true", help="从结构化 run report 记录本阶段通过结果。")
    parser.add_argument("--run-report", type=Path, default=RUN_REPORT_PATH, help="结构化 run report JSON 路径。")
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH, help=argparse.SUPPRESS)
    parser.add_argument("--status", type=Path, default=STATUS_PATH, help=argparse.SUPPRESS)
    args = parser.parse_args()

    INVENTORY_PATH = args.inventory
    STATUS_PATH = args.status

    table = parse_replacement_table()
    data = load_status()
    errors, status_items = validate_items(
        data,
        table,
        args.phase,
        args.pre_delete,
        enforce_phase_gate=not args.record_from_last_run,
    )
    if not errors and args.record_from_last_run:
        errors.extend(match_last_run_to_items(data, status_items, args.phase, args.pre_delete, args.run_report))
        if not errors:
            data = load_status()
            errors, status_items = validate_items(data, table, args.phase, args.pre_delete)

    if errors:
        print("替换状态检查失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"替换状态检查通过：替换表 {len(table)} 项，当前按 Phase {args.phase} 规则校验。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
