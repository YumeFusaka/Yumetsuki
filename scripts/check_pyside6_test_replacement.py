from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "tests" / "migration" / "replacement_status.json"

QT_PATTERNS = (
    re.compile(r"^\s*(from|import)\s+PySide6\b", re.MULTILINE),
    re.compile(r"\bQApplication\b"),
    re.compile(r"\bQObject\b"),
    re.compile(r"\bQThread\b"),
    re.compile(r"\bqtbot\b"),
    re.compile(r"\bQWidget\b"),
    re.compile(r"\bQPixmap\b"),
    re.compile(r"^\s*from\s+PySide6\.[^\n]*\bSignal\b", re.MULTILINE),
)


def normalize(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def load_replacement_items() -> dict[str, str]:
    data = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    return {
        normalize(item["legacy_test"]): item["retirement_action"]
        for item in data.get("items", [])
    }


def has_qt_dependency(text: str) -> bool:
    return any(pattern.search(text) for pattern in QT_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", type=int, default=0)
    args = parser.parse_args()

    if not STATUS_PATH.exists():
        print(f"缺少替换状态文件：{STATUS_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    replacement_items = load_replacement_items()
    errors: list[str] = []
    qt_hits: list[str] = []

    for path in sorted((ROOT / "tests").glob("test_*.py")):
        rel = normalize(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        if not has_qt_dependency(text):
            continue

        qt_hits.append(rel)
        action = replacement_items.get(rel)
        if action not in {"delete", "rewrite"}:
            errors.append(f"{rel} 命中 Qt / PySide6 关键字，但未登记为删除或同名改写")
        if args.phase >= 5 and action == "rewrite":
            errors.append(f"{rel} 是同名改写条目，Phase 5 后仍命中 Qt / PySide6 关键字")

    if errors:
        print("pyside6 test replacement failed", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"pyside6 test replacement ok ({len(qt_hits)} legacy Qt-bound tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
