from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = PROJECT_ROOT / "python_core" / "sidecar_main.py"
LOCAL_PREFIXES = ("python_core",)
FORBIDDEN_ROOTS = {"PySide6", "ui"}


def test_sidecar_import_graph_does_not_reach_qt_or_legacy_ui() -> None:
    visited: set[Path] = set()
    stack = [ENTRYPOINT]
    forbidden: list[str] = []

    while stack:
        path = stack.pop().resolve()
        if path in visited or not path.exists():
            continue
        visited.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = _imported_module(node, path)
            if module is None:
                continue
            root = module.split(".")[0]
            if root in FORBIDDEN_ROOTS:
                forbidden.append(f"{path.relative_to(PROJECT_ROOT).as_posix()} -> {module}")
                continue
            if root in LOCAL_PREFIXES:
                target = _module_to_path(module)
                if target is not None:
                    stack.append(target)

    assert not forbidden


def _imported_module(node: ast.AST, current_file: Path) -> str | None:
    if isinstance(node, ast.Import):
        return node.names[0].name
    if isinstance(node, ast.ImportFrom):
        if node.level:
            package = _package_for_relative_import(current_file, node.level)
            return ".".join(part for part in (package, node.module or "") if part)
        return node.module
    return None


def _package_for_relative_import(current_file: Path, level: int) -> str:
    relative = current_file.relative_to(PROJECT_ROOT).with_suffix("")
    parts = list(relative.parts[:-1])
    if level > 1:
        parts = parts[: -(level - 1)]
    return ".".join(parts)


def _module_to_path(module: str) -> Path | None:
    module_path = PROJECT_ROOT / Path(*module.split("."))
    if module_path.with_suffix(".py").exists():
        return module_path.with_suffix(".py")
    init_path = module_path / "__init__.py"
    if init_path.exists():
        return init_path
    return None
