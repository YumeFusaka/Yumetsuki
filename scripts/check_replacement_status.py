from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "tests" / "migration" / "test_inventory.md"
STATUS_PATH = ROOT / "tests" / "migration" / "replacement_status.json"


def normalize(path: str) -> str:
    return path.strip().replace("\\", "/")


def inventory_table_items() -> dict[str, str]:
    markdown = INVENTORY.read_text(encoding="utf-8")
    match = re.search(r"^## PySide6 绑定测试替换表\s*$", markdown, re.MULTILINE)
    if not match:
        raise ValueError("测试迁移清单缺少 PySide6 绑定测试替换表")
    items: dict[str, str] = {}
    for line in markdown[match.end() :].splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or not cells[0].startswith("`tests/test_"):
            continue
        legacy = normalize(cells[0].strip("`"))
        if cells[2] == "删除":
            action = "delete"
        elif cells[2] == "同名改写":
            action = "rewrite"
        else:
            raise ValueError(f"{legacy} 的退场动作非法：{cells[2]}")
        items[legacy] = action
    return items


def has_two_consecutive_passes(records: list[dict], current_phase: int, pre_delete: bool) -> bool:
    passed = sorted(
        {
            int(record.get("phase"))
            for record in records
            if record.get("result_summary") and int(record.get("phase", -1)) <= current_phase
        }
    )
    if pre_delete and current_phase == 5 and 5 not in passed:
        return False
    return any((phase + 1) in passed for phase in passed)


def validate_run_report(report_path: Path, phase: int) -> None:
    data = json.loads(report_path.read_text(encoding="utf-8"))
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("run report 缺少 records 数组")
    for record in records:
        required = {"phase", "command", "exit_code", "result_summary", "schema_hash", "executed_at"}
        missing = required - set(record)
        if missing:
            raise ValueError(f"run report 记录缺少字段：{', '.join(sorted(missing))}")
        if int(record["phase"]) != phase:
            raise ValueError("run report phase 与参数不一致")
        if int(record["exit_code"]) != 0:
            raise ValueError(f"run report 包含失败命令：{record['command']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, required=True)
    parser.add_argument("--record-from-last-run", action="store_true")
    parser.add_argument("--run-report", type=Path)
    parser.add_argument("--pre-delete", action="store_true")
    args = parser.parse_args()

    if not STATUS_PATH.exists():
        print(f"缺少替换状态文件：{STATUS_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1
    if not INVENTORY.exists():
        print(f"缺少测试迁移清单：{INVENTORY.relative_to(ROOT)}", file=sys.stderr)
        return 1

    try:
        expected = inventory_table_items()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    by_legacy = {normalize(item["legacy_test"]): item for item in data.get("items", [])}
    errors: list[str] = []

    if set(by_legacy) != set(expected):
        missing = sorted(set(expected) - set(by_legacy))
        extra = sorted(set(by_legacy) - set(expected))
        if missing:
            errors.append("replacement_status.json 缺少条目：\n  " + "\n  ".join(missing))
        if extra:
            errors.append("replacement_status.json 存在清单外条目：\n  " + "\n  ".join(extra))

    for legacy, action in expected.items():
        item = by_legacy.get(legacy)
        if not item:
            continue
        if item.get("retirement_action") != action:
            errors.append(f"{legacy} 的 retirement_action 应为 {action}")
        replacements = item.get("replacement_tests")
        if not isinstance(replacements, list) or not replacements:
            errors.append(f"{legacy} 缺少 replacement_tests")
        if item.get("delete_approved") is not False and args.phase < 5:
            errors.append(f"{legacy} 在 Phase 5 前不得 delete_approved=true")

    if args.record_from_last_run:
        if not args.run_report:
            errors.append("--record-from-last-run 必须提供 --run-report，不能用人工摘要冒充真实执行结果")
        else:
            try:
                validate_run_report(args.run_report, args.phase)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(str(exc))

    if args.phase >= 5:
        for legacy, item in sorted(by_legacy.items()):
            records = item.get("phase_pass_records", [])
            if not has_two_consecutive_passes(records, args.phase, args.pre_delete):
                errors.append(f"{legacy} 缺少连续两个阶段通过记录")
            if item.get("retirement_action") == "delete" and item.get("delete_approved") is not True and not args.pre_delete:
                errors.append(f"{legacy} 尚未 delete_approved=true，不能删除旧测试")

    if errors:
        print("replacement status failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("replacement status ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
