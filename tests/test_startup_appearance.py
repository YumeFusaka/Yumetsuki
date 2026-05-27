from PySide6.QtWidgets import QApplication

from config.schema import SystemConfig
from main import bring_window_to_front
from ui.settings.pages.system_page import SystemPage
from ui.theme import apply_system_appearance


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeStartupWindow:
    def __init__(self):
        self.show_normal_calls = 0
        self.raise_calls = 0
        self.activate_calls = 0

    def showNormal(self):
        self.show_normal_calls += 1

    def raise_(self):
        self.raise_calls += 1

    def activateWindow(self):
        self.activate_calls += 1


def test_apply_system_appearance_sets_app_font_and_sakura_theme():
    app = _app()
    config = SystemConfig(theme="dark", font_family="Courier New", font_size=17)

    apply_system_appearance(app, config)

    assert config.theme == "sakura"
    assert app.font().family() == "Courier New"
    assert app.font().pointSize() == 17


def test_system_page_language_is_disabled_and_theme_applies_sakura():
    _app()
    config = SystemConfig(language="en-US", theme="dark")
    page = SystemPage(config)

    assert not page._language.isEnabled()
    assert page._language.currentData() == "zh-CN"
    assert "当前仅支持简体中文" in page._language.toolTip()
    assert page._theme.currentData() == "sakura"

    page.apply()

    assert config.language == "zh-CN"
    assert config.theme == "sakura"


def test_main_bring_window_to_front_uses_show_normal_raise_activate():
    window = _FakeStartupWindow()

    bring_window_to_front(window)

    assert window.show_normal_calls == 1
    assert window.raise_calls == 1
    assert window.activate_calls == 1
