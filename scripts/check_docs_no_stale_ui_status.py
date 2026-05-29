from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DOCS = [
    Path("README.md"),
    Path("CLAUDE.md"),
    Path("docs/README.md"),
    Path("docs/architecture.md"),
    Path("docs/development.md"),
    Path("docs/ui-guidelines.md"),
]

PHASE5_STALE_PATTERNS = [
    ("pyside6_current_main", re.compile(r"(当前主\s*UI\s*[：:]\s*PySide6|当前实现仍以\s*PySide6\s*为主\s*UI)")),
    ("migration_not_started", re.compile(r"(尚未实施|尚未进入代码实施|等待进入实施计划|实施尚未开始)")),
    ("pyside6_project_identity", re.compile(r"Python\s*/\s*PySide6\s*桌宠")),
    ("phase01_state", re.compile(r"Phase\s*0/1")),
    ("legacy_dual_run", re.compile(r"(legacy\s*双跑|双跑参考|旧\s*PySide6.*(保留|参考)|PySide6.*legacy)")),
    ("tauri_building_not_current", re.compile(r"(新主线建设中|建设中|迁移实施已开始|当前处于\s*Phase)")),
    ("pending_delete_confirmation", re.compile(r"(仍在仓库中|等待.*删除.*确认|等待用户确认.*删除|等待删除确认)")),
    ("legacy_pyside6_runnable", re.compile(r"Legacy\s+PySide6\s+当前仍可运行", re.IGNORECASE)),
    ("legacy_main_entry", re.compile(r"\bpython\s+main\.py\b", re.IGNORECASE)),
    ("phase1_directory_pending", re.compile(r"Phase\s*1.*(建立后|目录建立后|前端骨架)")),
    ("qt_control_reference", re.compile(r"\b(QComboBox|QFontDatabase|QTextEdit|QMenu|QToolTip|QThread|QMediaPlayer)\b")),
    ("legacy_ui_path_reference", re.compile(r"\bui[\\/](assets|theme|chat|settings)\b")),
]

PHASE01_REQUIRED_PATTERNS = [
    re.compile(r"Phase\s*0/1"),
    re.compile(r"PySide6.*(双跑|参考|回归基线|legacy)"),
    re.compile(r"Tauri.*(建设|迁移|目标|新主线)"),
]


@dataclass(frozen=True)
class Finding:
    path: Path
    line_no: int
    rule_id: str
    line: str


def _iter_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _is_archive(path: Path) -> bool:
    normalized = path.as_posix().lower()
    return "/superpowers/specs/" in normalized or "/superpowers/plans/" in normalized or "/superpowers/brainstorms/" in normalized


def scan_phase5(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.is_file() or _is_archive(path):
            continue
        for line_no, line in enumerate(_iter_lines(path), start=1):
            for rule_id, pattern in PHASE5_STALE_PATTERNS:
                if pattern.search(line):
                    findings.append(Finding(path, line_no, rule_id, line.strip()))
    return findings


def scan_phase01(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        if not path.is_file() or _is_archive(path):
            continue
        text = "\n".join(_iter_lines(path))
        if "Tauri" not in text and "PySide6" not in text:
            continue
        for index, pattern in enumerate(PHASE01_REQUIRED_PATTERNS, start=1):
            if not pattern.search(text):
                findings.append(Finding(path, 1, f"phase01_required_{index}", "缺少 Phase 0/1 迁移状态或双跑说明"))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="扫描文档入口中过期 UI 迁移状态")
    parser.add_argument("--phase", choices=["0", "1", "5"], default="5")
    parser.add_argument("--path", dest="paths", type=Path, action="append")
    args = parser.parse_args(argv)

    paths = args.paths or DEFAULT_DOCS
    findings = scan_phase5(paths) if args.phase == "5" else scan_phase01(paths)
    if findings:
        for finding in findings:
            print(
                f"{finding.path}:{finding.line_no}: {finding.rule_id}: {finding.line}",
                file=sys.stderr,
            )
        return 1

    if args.phase == "5":
        print("Phase 5 文档 stale 扫描通过")
    else:
        print("Phase 0/1 文档状态扫描通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
