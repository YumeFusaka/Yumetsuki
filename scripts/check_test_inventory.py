from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "tests" / "migration" / "test_inventory.md"
LEGACY_SECTIONS = ("Python Core 保留", "Tauri / Vue 替换", "Headless 同名改写")
NESTED_SECTION = "新增迁移测试清单"
RETIRED_SECTION = "已退场旧测试"


def normalize(path: str) -> str:
    return path.strip().replace("\\", "/")


def run_rg_tests() -> set[str]:
    result = subprocess.run(
        ["rg", "--files", "tests", "-g", "test_*.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        print(result.stderr.strip() or "rg 执行失败", file=sys.stderr)
        sys.exit(1)
    return {normalize(line) for line in result.stdout.splitlines() if line.strip()}


def section_text(markdown: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\s*$", markdown, re.MULTILINE)
    if not match:
        raise ValueError(f"缺少清单章节：{title}")
    next_match = re.search(r"^## ", markdown[match.end() :], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(markdown)
    return markdown[match.end() : end]


def paths_in_text(text: str) -> set[str]:
    return {normalize(path) for path in re.findall(r"`([^`]+test_[^`]+?\.py)`", text)}


def replacement_table_legacy(markdown: str) -> set[str]:
    table = section_text(markdown, "PySide6 绑定测试替换表")
    return {normalize(path) for path in re.findall(r"\|\s*`(tests/test_[^`]+?\.py)`\s*\|", table)}


def main() -> int:
    if not INVENTORY.exists():
        print(f"缺少测试迁移清单：{INVENTORY.relative_to(ROOT)}", file=sys.stderr)
        return 1

    actual = run_rg_tests()
    markdown = INVENTORY.read_text(encoding="utf-8")
    legacy_by_section = {
        section: paths_in_text(section_text(markdown, section)) for section in LEGACY_SECTIONS
    }
    retired = paths_in_text(section_text(markdown, RETIRED_SECTION))
    nested_registered = paths_in_text(section_text(markdown, NESTED_SECTION))
    replacement_legacy = replacement_table_legacy(markdown)
    errors: list[str] = []

    seen: dict[str, list[str]] = {}
    for section, paths in legacy_by_section.items():
        for path in paths:
            seen.setdefault(path, []).append(section)
    for path, sections in sorted(seen.items()):
        if len(sections) > 1:
            errors.append(f"{path} 同时出现在互斥分类：{', '.join(sections)}")

    top_actual = {path for path in actual if re.fullmatch(r"tests/test_[^/]+\.py", path)}
    nested_actual = actual - top_actual
    legacy_registered = set().union(*legacy_by_section.values())

    missing_top = sorted((top_actual - retired) - legacy_registered)
    stale_top = sorted((legacy_registered - retired) - top_actual)
    extra_nested = sorted(nested_actual - nested_registered)
    if missing_top:
        errors.append("未登记的顶层 legacy 测试：\n  " + "\n  ".join(missing_top))
    if stale_top:
        errors.append("清单中登记但实际不存在的 legacy 测试：\n  " + "\n  ".join(stale_top))
    if extra_nested:
        errors.append("未登记的嵌套迁移测试：\n  " + "\n  ".join(extra_nested))

    replacement_expected = legacy_by_section["Tauri / Vue 替换"] | legacy_by_section["Headless 同名改写"]
    table_missing = sorted(replacement_expected - replacement_legacy)
    if table_missing:
        errors.append("替换分类缺少 PySide6 绑定测试替换表条目：\n  " + "\n  ".join(table_missing))

    if errors:
        print("tests inventory failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("tests inventory ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
