from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = [
    PROJECT_ROOT / name
    for name in (
        "python_core",
        "agent",
        "core",
        "vision",
        "config",
        "llm",
        "memory",
        "session",
        "stt",
        "tts",
        "plugins",
    )
    if (PROJECT_ROOT / name).exists()
]
FORBIDDEN_IMPORTS = {"PySide6"}
FORBIDDEN_TEXT = ("PySide6", "QtWebEngine", "QApplication", "QObject", "QThread", "Signal", "ui.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan sidecar code for PySide6/Qt imports.")
    parser.add_argument("--root", action="append", type=Path, help="Additional root to scan")
    args = parser.parse_args(argv)

    roots = args.root or DEFAULT_SCAN_ROOTS
    findings: list[str] = []
    for root in roots:
        root = root.resolve()
        if root.is_file():
            paths = [root]
        else:
            paths = sorted(root.rglob("*.py"))
        for path in paths:
            findings.extend(scan_file(path))

    if findings:
        sys.stderr.write("\n".join(findings) + "\n")
        return 1
    return 0


def scan_file(path: Path) -> list[str]:
    relative = _display(path)
    text = path.read_text(encoding="utf-8")
    findings: list[str] = []
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [f"{relative}:{exc.lineno}: syntax error: {exc.msg}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in FORBIDDEN_IMPORTS:
                    findings.append(f"{relative}:{node.lineno}: forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".")[0] in FORBIDDEN_IMPORTS or module.startswith("ui."):
                findings.append(f"{relative}:{node.lineno}: forbidden import from {module}")
        elif isinstance(node, ast.Call):
            if _is_dynamic_forbidden_import(node):
                findings.append(f"{relative}:{node.lineno}: forbidden dynamic Qt import")

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for token in FORBIDDEN_TEXT:
            if token in line:
                findings.append(f"{relative}:{lineno}: forbidden Qt token {token}")
    return findings


def _is_dynamic_forbidden_import(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "__import__":
        return bool(node.args and _constant_startswith(node.args[0], ("PySide6", "ui.")))
    if isinstance(func, ast.Attribute) and func.attr == "import_module":
        return bool(node.args and _constant_startswith(node.args[0], ("PySide6", "ui.")))
    return False


def _constant_startswith(node: ast.AST, prefixes: tuple[str, ...]) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith(prefixes)


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
