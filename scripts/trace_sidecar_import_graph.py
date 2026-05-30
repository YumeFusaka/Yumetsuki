from __future__ import annotations

import builtins
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODULE_PREFIXES = ("PySide6", "ui")
FORBIDDEN_SOURCE_TOKENS = (
    "from PySide6",
    "import PySide6",
    'importlib.import_module("PySide6',
    "__import__(\"PySide6",
    "QtWebEngine",
    "PySide6",
    "QApplication",
    "QObject",
    "QThread",
    "Signal",
)


def trace_import_graph(root_module: str = "python_core.sidecar_main") -> dict[str, Any]:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    before = set(sys.modules)
    importers: dict[str, str | None] = {}
    original_import = builtins.__import__

    def traced_import(name: str, globals=None, locals=None, fromlist=(), level: int = 0):  # type: ignore[no-untyped-def]
        importer = globals.get("__name__") if isinstance(globals, dict) else None
        module = original_import(name, globals, locals, fromlist, level)
        if level == 0:
            importers.setdefault(name, importer)
            for child in fromlist or ():
                if child == "*":
                    continue
                importers.setdefault(f"{name}.{child}", importer)
        return module

    builtins.__import__ = traced_import
    try:
        importlib.import_module(root_module)
    finally:
        builtins.__import__ = original_import

    module_names = sorted((set(sys.modules) - before) | {root_module})
    modules = [_module_record(name, sys.modules.get(name), importers.get(name)) for name in module_names]
    return {"root": root_module, "modules": [item for item in modules if item is not None]}


def find_forbidden_entries(graph: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for item in graph["modules"]:
        module = str(item["module"])
        if module.startswith(FORBIDDEN_MODULE_PREFIXES):
            findings.append(f"{module}: forbidden module reached from {item.get('importer')}")
        file_name = item.get("file")
        if not file_name or not item.get("is_project"):
            continue
        source = Path(str(file_name)).read_text(encoding="utf-8", errors="ignore")
        for token in FORBIDDEN_SOURCE_TOKENS:
            if token in source:
                findings.append(f"{file_name}: suspect token {token!r}")
    return findings


def _module_record(name: str, module: ModuleType | None, importer: str | None) -> dict[str, Any] | None:
    if module is None:
        return None
    file_name = getattr(module, "__file__", None)
    resolved = str(Path(file_name).resolve()) if file_name else None
    return {
        "module": name,
        "file": resolved,
        "importer": importer,
        "is_project": bool(resolved and _is_relative_to(Path(resolved), PROJECT_ROOT)),
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def main() -> int:
    graph = trace_import_graph()
    findings = find_forbidden_entries(graph)
    if findings:
        for finding in findings:
            sys.stderr.write(f"{finding}\n")
        return 1
    json.dump(graph, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
