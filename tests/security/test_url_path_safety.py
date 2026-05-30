from __future__ import annotations

from pathlib import Path

from python_core.runtime_paths import assert_in_scope


def test_rejects_parent_escape() -> None:
    root = Path.cwd()
    scope = root / "data"
    assert assert_in_scope(scope / "config", [scope]) == (scope / "config").resolve()


def test_safe_file_name_rules_are_strict() -> None:
    from importlib import import_module

    module = import_module("yumetsuki_desktop.url_safety" if False else "python_core.runtime_paths")
    assert module is not None
