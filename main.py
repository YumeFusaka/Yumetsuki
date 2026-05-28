import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from config.manager import ConfigManager
from ui.settings.window import SettingsWindow
from ui.startup import StartupLoadingWindow
from ui.theme import SAKURA_MENU_STYLE, SAKURA_TOOLTIP_STYLE, apply_system_appearance, install_sakura_menu_theme

APP_STYLE = """
QDialog, QInputDialog, QMessageBox {
    background: #fff5f7; color: #4a3040;
}
QDialog QLabel, QMessageBox QLabel, QInputDialog QLabel {
    color: #4a3040; font-size: 13px;
}
QDialog QLineEdit, QInputDialog QLineEdit {
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
}
QDialog QLineEdit:focus { border-color: #d4567a; }
QDialog QPushButton, QMessageBox QPushButton, QInputDialog QPushButton {
    background: rgba(255,200,210,0.4);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 13px;
}
QDialog QPushButton:hover, QMessageBox QPushButton:hover { background: rgba(255,154,162,0.4); }
QDialog QComboBox, QInputDialog QComboBox {
    background: rgba(255,255,255,0.8);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 10px;
    color: #4a3040; font-size: 13px;
}
""" + SAKURA_MENU_STYLE + SAKURA_TOOLTIP_STYLE


def bring_window_to_front(window) -> None:
    if hasattr(window, "showNormal"):
        window.showNormal()
    else:
        window.show()
    window.raise_()
    window.activateWindow()


def schedule_bring_window_to_front(window, delay_ms: int = 80) -> None:
    QTimer.singleShot(delay_ms, lambda: bring_window_to_front(window))


def _advance_startup(loading: StartupLoadingWindow | None, message: str, value: int, app: QApplication) -> None:
    if loading is not None:
        loading.update_progress(message, value)
        app.processEvents()


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    install_sakura_menu_theme(app)

    loading = StartupLoadingWindow()
    loading.show()
    _advance_startup(loading, "加载配置...", 25, app)

    config = ConfigManager()
    _advance_startup(loading, "应用外观...", 50, app)
    apply_system_appearance(app, config.system)

    _advance_startup(loading, "创建设置中心...", 75, app)
    window = SettingsWindow()

    _advance_startup(loading, "准备完成...", 100, app)
    window.show()
    loading.close()
    schedule_bring_window_to_front(window)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
