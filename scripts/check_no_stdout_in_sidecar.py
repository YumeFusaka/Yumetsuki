from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCAN_ROOTS = [PROJECT_ROOT / "python_core"]
ALLOWED_STDOUT_WRITE_FILES = {
    (PROJECT_ROOT / "python_core" / "rpc" / "framing.py").resolve(),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan sidecar code for stdout pollution.")
    parser.add_argument("--root", action="append", type=Path, help="Additional root to scan")
    args = parser.parse_args(argv)

    findings: list[str] = []
    roots = args.root or DEFAULT_SCAN_ROOTS
    for root in roots:
        root = root.resolve()
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            findings.extend(scan_file(path))

    if findings:
        sys.stderr.write("\n".join(findings) + "\n")
        return 1
    return 0


def scan_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError as exc:
        return [f"{_display(path)}:{exc.lineno}: syntax error: {exc.msg}"]
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _is_print(node):
                findings.append(f"{_display(path)}:{node.lineno}: forbidden print() in sidecar path")
            elif _is_stdout_write(node) and path.resolve() not in ALLOWED_STDOUT_WRITE_FILES:
                findings.append(f"{_display(path)}:{node.lineno}: forbidden sys.stdout.write() in sidecar path")
            elif _is_stdout_logging_handler(node):
                findings.append(f"{_display(path)}:{node.lineno}: forbidden logging.StreamHandler(sys.stdout)")
    return findings


def _is_print(node: ast.Call) -> bool:
    return isinstance(node.func, ast.Name) and node.func.id == "print"


def _is_stdout_write(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr == "write"
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "stdout"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "sys"
    )


def _is_stdout_logging_handler(node: ast.Call) -> bool:
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "StreamHandler"):
        return False
    for arg in node.args:
        if isinstance(arg, ast.Attribute) and arg.attr == "stdout" and isinstance(arg.value, ast.Name) and arg.value.id == "sys":
            return True
    return False


def _display(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
