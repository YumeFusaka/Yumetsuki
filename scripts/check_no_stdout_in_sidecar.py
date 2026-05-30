from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

from trace_sidecar_import_graph import PROJECT_ROOT, trace_import_graph


NAKED_PRINT = re.compile(r"(?<![\w.])print\s*\(")
SYS_STDOUT_WRITE = re.compile(r"\bsys\.stdout\.write\s*\(")
LOGGING_STDOUT = re.compile(r"logging\.StreamHandler\s*\(\s*sys\.stdout\s*\)")


def scan_sidecar_graph() -> list[tuple[Path, int, str]]:
    graph = trace_import_graph()
    files = {
        Path(str(item["file"]))
        for item in graph["modules"]
        if item.get("is_project") and item.get("file")
    }
    gptsovits = PROJECT_ROOT / "tts" / "adapters" / "gptsovits.py"
    if gptsovits.exists():
        files.add(gptsovits)
    return scan_files(sorted(files))


def scan_files(files: Iterable[Path]) -> list[tuple[Path, int, str]]:
    findings: list[tuple[Path, int, str]] = []
    for file_name in files:
        if _is_ignored(file_name):
            continue
        for line_number, line in enumerate(file_name.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if _is_allowed(line):
                continue
            if NAKED_PRINT.search(line) or SYS_STDOUT_WRITE.search(line) or LOGGING_STDOUT.search(line):
                findings.append((file_name, line_number, line.strip()))
    return findings


def _is_allowed(line: str) -> bool:
    return "sidecar_stderr_logger" in line or "builtins.print" in line


def _is_ignored(path: Path) -> bool:
    normalized = path.resolve()
    ignored_parts = {"tests", "migration_archive"}
    return bool(set(normalized.parts) & ignored_parts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path)
    args = parser.parse_args(argv)
    findings = scan_files(args.artifact.rglob("*.py")) if args.artifact else scan_sidecar_graph()
    if findings:
        for file_name, line_number, snippet in findings:
            relative = file_name.resolve().relative_to(PROJECT_ROOT)
            sys.stderr.write(f"{relative}:{line_number}: {snippet}\n")
        return 1
    sys.stdout.write("sidecar stdout scan ok\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
