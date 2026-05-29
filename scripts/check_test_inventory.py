from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "tests" / "migration" / "test_inventory.md"

LEGACY_SECTIONS = {
    "Python Core 保留": "python_core",
    "Tauri / Vue 替换": "tauri_vue",
    "Headless 同名改写": "headless_rewrite",
}
NEW_SECTION = "新增迁移测试清单"
RETIRED_SECTION = "已退场旧测试"
TABLE_HEADER = "| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |"
KNOWN_GATE_COMMANDS = {
    "npm test",
    "npm run test:a11y",
    "npm run e2e:startup",
    "npm run e2e:settings",
    "npm run e2e:chat",
    "npm run e2e:logs-tools",
    "npm run e2e:stress",
    "cargo test --test media_contract",
}
PHASE5_CAPABILITY_KEYWORDS = {
    "settings": ("settings", "设置"),
    "chat": ("chat", "聊天", "TTS", "STT", "被动气泡", "窗口缩放", "立绘", "录音", "音频"),
    "logs": ("logs", "日志", "log"),
    "plugins": ("plugin", "插件"),
    "mcp": ("mcp", "MCP"),
    "diagnostics": ("diagnostic", "诊断"),
    "startup": ("startup", "启动"),
    "event bridge": ("event_publisher", "ui_event_bridge", "事件桥", "RpcEventPublisher"),
}


@dataclass(frozen=True)
class ReplacementRow:
    legacy_test: str
    action: str
    replacement_layer: str
    targets: tuple[str, ...]
    phase: str


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def extract_backtick_values(value: str) -> list[str]:
    return [normalize_path(match) for match in re.findall(r"`([^`]+)`", value)]


def section_name(line: str) -> str | None:
    if line.startswith("## ") and not line.startswith("### "):
        return line[3:].strip()
    return None


def read_inventory() -> str:
    if not INVENTORY_PATH.exists():
        raise SystemExit(f"缺少迁移清单：{INVENTORY_PATH.relative_to(ROOT)}")
    return INVENTORY_PATH.read_text(encoding="utf-8")


def parse_bullet_sections(text: str) -> dict[str, list[str]]:
    current: str | None = None
    sections: dict[str, list[str]] = {name: [] for name in LEGACY_SECTIONS}
    sections[NEW_SECTION] = []
    sections[RETIRED_SECTION] = []

    for line in text.splitlines():
        maybe_section = section_name(line)
        if maybe_section is not None:
            current = maybe_section
            continue
        if current not in sections:
            continue
        if not line.lstrip().startswith("- "):
            continue
        sections[current].extend(extract_backtick_values(line))
    return sections


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_replacement_table(text: str) -> list[ReplacementRow]:
    rows: list[ReplacementRow] = []
    in_table = False
    for line in text.splitlines():
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
        rows.append(
            ReplacementRow(
                legacy_test=legacy_values[0],
                action=cells[2],
                replacement_layer=cells[3],
                targets=tuple(extract_backtick_values(cells[4])),
                phase=cells[5],
            )
        )
    if not rows:
        raise SystemExit("未找到 PySide6 绑定测试替换表")
    return rows


def actual_test_files() -> set[str]:
    if shutil.which("rg"):
        completed = subprocess.run(
            ["rg", "--files", "tests", "-g", "test_*.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode in (0, 1):
            return {
                normalize_path(line)
                for line in completed.stdout.splitlines()
                if line.strip()
            }
        print(completed.stderr, file=sys.stderr)
    return {
        normalize_path(str(path.relative_to(ROOT)))
        for path in (ROOT / "tests").rglob("test_*.py")
    }


def is_top_level_test(path: str) -> bool:
    return bool(re.fullmatch(r"tests/test_[^/]+\.py", path))


def path_exists_or_glob(target: str) -> bool:
    if any(char in target for char in "*?["):
        return any(ROOT.glob(target))
    return (ROOT / target).exists()


def is_command_covered(target: str) -> bool:
    if target.startswith("python -m pytest tests/rpc_contract/"):
        return True
    return target in KNOWN_GATE_COMMANDS


def has_table_coverage(row: ReplacementRow) -> bool:
    return any(path_exists_or_glob(target) or is_command_covered(target) for target in row.targets)


def format_paths(paths: set[str]) -> str:
    return "\n".join(f"  - {path}" for path in sorted(paths))


def find_duplicate_memberships(sections: dict[str, list[str]]) -> dict[str, list[str]]:
    memberships: dict[str, list[str]] = {}
    for section in LEGACY_SECTIONS:
        for path in sections[section]:
            memberships.setdefault(path, []).append(section)
    return {path: names for path, names in memberships.items() if len(names) > 1}


def check_phase5_capability_coverage(rows: list[ReplacementRow], errors: list[str]) -> None:
    searchable = "\n".join(
        f"{row.legacy_test} {row.replacement_layer} {' '.join(row.targets)}" for row in rows
    ).lower()
    for capability, keywords in PHASE5_CAPABILITY_KEYWORDS.items():
        if not any(keyword.lower() in searchable for keyword in keywords):
            errors.append(f"Phase 5 替代覆盖缺少能力：{capability}")


def main() -> int:
    parser = argparse.ArgumentParser(description="检查测试迁移清单与实际测试文件是否一致。")
    parser.add_argument("--phase", type=int, default=0, help="迁移阶段，Phase 5 会启用额外退场覆盖检查。")
    args = parser.parse_args()

    text = read_inventory()
    sections = parse_bullet_sections(text)
    rows = parse_replacement_table(text)
    actual = actual_test_files()
    actual_top = {path for path in actual if is_top_level_test(path)}
    actual_nested = actual - actual_top

    legacy_declared: set[str] = set()
    for section in LEGACY_SECTIONS:
        legacy_declared.update(sections[section])
    new_declared = set(sections[NEW_SECTION])
    retired_declared = set(sections[RETIRED_SECTION])

    errors: list[str] = []
    duplicates = find_duplicate_memberships(sections)
    if duplicates:
        details = "\n".join(
            f"  - {path}: {', '.join(names)}" for path, names in sorted(duplicates.items())
        )
        errors.append(f"legacy 互斥分类重复：\n{details}")

    duplicate_with_retired = legacy_declared & retired_declared
    if duplicate_with_retired:
        errors.append(f"已退场旧测试不能仍在 legacy 分类：\n{format_paths(duplicate_with_retired)}")

    missing_top = actual_top - legacy_declared - retired_declared
    if missing_top:
        errors.append(f"实际顶层测试未登记到 legacy 分类：\n{format_paths(missing_top)}")

    stale_legacy = legacy_declared - actual_top
    if stale_legacy:
        errors.append(f"legacy 分类登记了不存在的顶层测试：\n{format_paths(stale_legacy)}")

    retired_still_exists = retired_declared & actual_top
    if retired_still_exists:
        errors.append(f"已退场旧测试仍然存在于 tests/ 顶层：\n{format_paths(retired_still_exists)}")

    missing_nested = actual_nested - new_declared
    if missing_nested:
        errors.append(f"实际嵌套测试未登记到新增迁移测试清单：\n{format_paths(missing_nested)}")

    stale_new = new_declared - actual_nested
    if stale_new:
        errors.append(f"新增迁移测试清单登记了不存在的嵌套测试：\n{format_paths(stale_new)}")

    table_by_legacy = {row.legacy_test: row for row in rows}
    duplicated_table_paths = {
        row.legacy_test for row in rows if sum(1 for other in rows if other.legacy_test == row.legacy_test) > 1
    }
    if duplicated_table_paths:
        errors.append(f"替换表旧测试重复：\n{format_paths(duplicated_table_paths)}")

    expected_replaced = set(sections["Tauri / Vue 替换"]) | set(sections["Headless 同名改写"]) | retired_declared
    missing_table_rows = expected_replaced - set(table_by_legacy)
    if missing_table_rows:
        errors.append(f"替换类 legacy 测试缺少替换表条目：\n{format_paths(missing_table_rows)}")

    extra_table_rows = set(table_by_legacy) - expected_replaced
    if extra_table_rows:
        errors.append(f"替换表包含非替换类 legacy 测试：\n{format_paths(extra_table_rows)}")

    for row in rows:
        if row.action not in {"删除", "同名改写"}:
            errors.append(f"{row.legacy_test} 的退场动作非法：{row.action}")
        if not row.targets:
            errors.append(f"{row.legacy_test} 缺少新测试文件或命令")
        elif not has_table_coverage(row):
            errors.append(f"{row.legacy_test} 的替换项既没有真实文件，也没有已知 Phase gate 命令覆盖")
        if row.legacy_test in retired_declared and row.action != "删除":
            errors.append(f"{row.legacy_test} 已退场但退场动作不是删除")

    if args.phase >= 5:
        check_phase5_capability_coverage(rows, errors)

    if errors:
        print("测试迁移清单检查失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        f"测试迁移清单检查通过：顶层 legacy {len(actual_top)} 个，"
        f"嵌套迁移测试 {len(actual_nested)} 个，替换表 {len(rows)} 项。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
