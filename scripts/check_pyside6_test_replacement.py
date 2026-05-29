from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "tests" / "migration" / "test_inventory.md"
KEYWORDS = {"PySide6", "QApplication", "QObject", "QThread", "Signal", "qtbot", "QWidget", "QPixmap"}
TABLE_HEADER = "| 旧测试 | Qt / PySide6 依赖点 | 退场动作 | 替代层 | 新测试文件 / 命令 | 双跑阶段 | 删除条件 | 回滚方式 |"


@dataclass(frozen=True)
class ReplacementRow:
    legacy_test: str
    action: str


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/")


def extract_backtick_values(value: str) -> list[str]:
    return [normalize_path(match) for match in re.findall(r"`([^`]+)`", value)]


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_replacement_table() -> dict[str, ReplacementRow]:
    if not INVENTORY_PATH.exists():
        raise SystemExit(f"缺少迁移清单：{INVENTORY_PATH.relative_to(ROOT)}")
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
        rows[legacy] = ReplacementRow(legacy_test=legacy, action=cells[2])
    if not rows:
        raise SystemExit("未找到 PySide6 绑定测试替换表")
    return rows


def top_level_tests() -> list[Path]:
    return sorted((ROOT / "tests").glob("test_*.py"))


def keyword_hits(path: Path) -> set[str]:
    source = path.read_text(encoding="utf-8")
    hits: set[str] = set()
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type == tokenize.NAME and token.string in KEYWORDS:
                hits.add(token.string)
    except tokenize.TokenError:
        for keyword in KEYWORDS:
            if re.search(rf"\b{re.escape(keyword)}\b", source):
                hits.add(keyword)
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="检查顶层 PySide6/Qt 绑定测试是否有替换计划。")
    parser.add_argument("--phase", type=int, default=0, help="迁移阶段，Phase 5 会禁止同名改写测试继续含 Qt 关键字。")
    args = parser.parse_args()

    table = parse_replacement_table()
    errors: list[str] = []
    hit_files: dict[str, set[str]] = {}

    for path in top_level_tests():
        relative = normalize_path(str(path.relative_to(ROOT)))
        hits = keyword_hits(path)
        if not hits:
            continue
        hit_files[relative] = hits
        row = table.get(relative)
        if row is None:
            errors.append(f"{relative} 命中 {', '.join(sorted(hits))}，但不在 PySide6 绑定测试替换表")
            continue
        if row.action not in {"删除", "同名改写"}:
            errors.append(f"{relative} 的替换表退场动作非法：{row.action}")
            continue
        if args.phase >= 5 and row.action == "同名改写":
            errors.append(f"Phase 5 后同名改写测试仍含 Qt 关键字：{relative} -> {', '.join(sorted(hits))}")

    if errors:
        print("PySide6 测试替换扫描失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"PySide6 测试替换扫描通过：命中 {len(hit_files)} 个顶层测试文件，均已有替换表条目。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
