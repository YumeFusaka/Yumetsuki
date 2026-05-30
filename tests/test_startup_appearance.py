from PySide6.QtWidgets import QApplication

from config.schema import SystemConfig
from main import bring_window_to_front
from ui.startup.loading_window import StartupLoadingWindow
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


class _FakeMousePosition:
    def __init__(self, point):
        self._point = point

    def toPoint(self):
        return self._point


class _FakeMouseEvent:
    def __init__(self, point, *, button=None, buttons=None):
        self._point = point
        self._button = button
        self._buttons = buttons
        self.accepted = False

    def button(self):
        return self._button

    def buttons(self):
        return self._buttons

    def globalPosition(self):
        return _FakeMousePosition(self._point)

    def accept(self):
        self.accepted = True


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


def test_startup_loading_window_moves_when_dragged():
    from PySide6.QtCore import QPoint, Qt

    _app()
    window = StartupLoadingWindow()
    window.move(40, 50)

    press = _FakeMouseEvent(QPoint(100, 120), button=Qt.MouseButton.LeftButton)
    move = _FakeMouseEvent(QPoint(135, 155), buttons=Qt.MouseButton.LeftButton)
    release = _FakeMouseEvent(QPoint(135, 155), button=Qt.MouseButton.LeftButton)

    window.mousePressEvent(press)
    window.mouseMoveEvent(move)
    window.mouseReleaseEvent(release)

    assert press.accepted is True
    assert move.accepted is True
    assert release.accepted is True
    assert window.pos() == QPoint(75, 85)
    assert window._drag_offset is None

    window.close()
