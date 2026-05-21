from PySide6.QtWidgets import QMessageBox, QWidget


FEEDBACK_STYLE = """
QDialog, QMessageBox {
    background: #fff5f7; color: #4a3040;
}
QLabel {
    color: #4a3040; font-size: 13px;
}
QPushButton {
    background: rgba(255,200,210,0.4);
    border: 1px solid rgba(220,160,180,0.3);
    border-radius: 6px; padding: 6px 16px;
    color: #6b4a5a; font-size: 13px;
}
QPushButton:hover { background: rgba(255,154,162,0.4); }
"""


def confirm_action(parent: QWidget, title: str, message: str) -> bool:
    dlg = QMessageBox(parent)
    dlg.setStyleSheet(FEEDBACK_STYLE)
    dlg.setWindowTitle(title)
    dlg.setText(message)
    dlg.setIcon(QMessageBox.Icon.Question)
    dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    return dlg.exec() == QMessageBox.StandardButton.Yes


def show_feedback(parent: QWidget, title: str, message: str, *, success: bool = True) -> None:
    dlg = QMessageBox(parent)
    dlg.setStyleSheet(FEEDBACK_STYLE)
    dlg.setWindowTitle(title)
    dlg.setText(message)
    dlg.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning)
    dlg.setStandardButtons(QMessageBox.StandardButton.Ok)
    dlg.exec()
