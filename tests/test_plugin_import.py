from pathlib import Path

from ui.settings.pages.plugin_page import _copy_plugin_dir


def test_copy_plugin_dir_requires_plugin_py(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    dest_root = tmp_path / "plugins"

    result = _copy_plugin_dir(src, dest_root)

    assert result is None
    assert not dest_root.exists()


def test_copy_plugin_dir_copies_valid_plugin(tmp_path):
    src = tmp_path / "hello_plugin"
    src.mkdir()
    (src / "plugin.py").write_text("class Plugin: pass", encoding="utf-8")
    (src / "README.md").write_text("hello", encoding="utf-8")
    dest_root = tmp_path / "plugins"

    result = _copy_plugin_dir(src, dest_root)

    assert result == dest_root / "hello_plugin"
    assert (result / "plugin.py").exists()
    assert (result / "README.md").read_text(encoding="utf-8") == "hello"
