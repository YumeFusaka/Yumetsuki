from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QMenu


SAKURA_MENU_STYLE = """
QMenu {
    background: #fffafc;
    border: 1px solid rgba(220, 160, 180, 0.35);
    border-radius: 8px;
    padding: 6px;
    color: #4a3040;
}
QMenu::item {
    background: transparent;
    padding: 7px 24px 7px 12px;
    border-radius: 6px;
    color: #4a3040;
}
QMenu::item:selected {
    background: rgba(255, 222, 232, 0.95);
    color: #9b3060;
}
QMenu::separator {
    height: 1px;
    background: rgba(220, 160, 180, 0.25);
    margin: 5px 8px;
}
"""


def apply_sakura_menu_theme(menu: QMenu) -> None:
    menu.setStyleSheet(SAKURA_MENU_STYLE)
    palette = menu.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#fffafc"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#4a3040"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#4a3040"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#ffdee8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#9b3060"))
    menu.setPalette(palette)
    menu.setAutoFillBackground(True)


class SakuraMenuEventFilter(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QMenu) and event.type() in {
            QEvent.Type.Polish,
            QEvent.Type.Show,
            QEvent.Type.ShowToParent,
        }:
            apply_sakura_menu_theme(watched)
        return super().eventFilter(watched, event)


def install_sakura_menu_theme(app: QApplication | None = None) -> None:
    app = app or QApplication.instance()
    if app is None:
        return
    if getattr(app, "_sakura_menu_event_filter", None) is None:
        event_filter = SakuraMenuEventFilter(app)
        app.installEventFilter(event_filter)
        app._sakura_menu_event_filter = event_filter
    if "QMenu {" not in app.styleSheet():
        app.setStyleSheet(app.styleSheet() + "\n" + SAKURA_MENU_STYLE)
