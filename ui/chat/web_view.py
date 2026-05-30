from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel


class ChatBridge(QObject):
    user_message = Signal(str)

    @Slot(str)
    def send_message(self, text: str):
        self.user_message.emit(text)


class ChatWebView(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bridge = ChatBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)
        self.page().setBackgroundColor(self.palette().window().color())

        template_dir = Path(__file__).parent / "templates"
        self.setUrl(QUrl.fromLocalFile(str(template_dir / "chat.html")))

    @property
    def bridge(self) -> ChatBridge:
        return self._bridge

    def add_user_message(self, text: str):
        self.page().runJavaScript(f"addMessage('user', {repr(text)});")

    def start_assistant_message(self):
        self.page().runJavaScript("startAssistantMessage();")

    def update_assistant_message(self, text: str):
        escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        self.page().runJavaScript(f"updateLastAssistant(`{escaped}`);")
