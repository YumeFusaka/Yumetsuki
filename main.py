import sys
from PySide6.QtWidgets import QApplication
from ui.settings.window import SettingsWindow
from ui.theme import SAKURA_MENU_STYLE, install_sakura_menu_theme

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
QToolTip {
    background: #fff0f3; color: #4a3040;
    border: 1px solid rgba(220,160,180,0.4);
    border-radius: 4px; padding: 4px 8px;
    font-size: 12px;
}
""" + SAKURA_MENU_STYLE


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLE)
    install_sakura_menu_theme(app)
    app.setFont(app.font())  # Ensure font size is valid

    window = SettingsWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
