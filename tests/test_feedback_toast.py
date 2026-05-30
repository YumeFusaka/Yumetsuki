from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QLabel, QWidget

from config.schema import SystemConfig
from ui.settings.feedback import ConfirmDialog
from ui.settings.feedback import ToastMessage
from ui.text_metrics import longest_line_width


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_toast_expands_to_single_line_text_until_max_width():
    _app()
    host = QWidget()
    host.resize(900, 600)
    message = "桌宠对话窗口已启动，正在加载记忆..."
    toast = ToastMessage(message, True, host)
    try:
        body_label = toast.findChild(QLabel, "bodyLabel")
        assert body_label is not None

        text_width = longest_line_width(body_label, message)
        expected_min_width = text_width + ToastMessage._chrome_width()

        assert toast.width() >= expected_min_width
        assert body_label.width() >= text_width
        assert body_label.maximumWidth() >= text_width
        assert toast.width() <= ToastMessage.MAX_WIDTH
        assert toast.width() <= host.width() - ToastMessage.MARGIN * 2
    finally:
        toast.close()
        host.close()


def test_feedback_dialogs_use_settings_font_tokens():
    _app()
    host = QWidget()
    host._config = SimpleNamespace(system=SystemConfig(font_size=24))
    host.resize(900, 600)

    confirm = ConfirmDialog("确认", "是否继续？", host)
    toast = ToastMessage("操作已完成", True, host)
    try:
        title = confirm.findChild(QLabel, "titleLabel")
        body = confirm.findChild(QLabel, "bodyLabel")
        toast_body = toast.findChild(QLabel, "bodyLabel")

        assert title is not None and "font-size: 20px" in title.styleSheet()
        assert body is not None and "font-size: 16px" in body.styleSheet()
        assert toast_body is not None and "font-size: 15px" in toast_body.styleSheet()
    finally:
        confirm.close()
        toast.close()
        host.close()
