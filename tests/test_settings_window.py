from PySide6.QtWidgets import QApplication, QPushButton

from config.schema import LLMConfig
from ui.chat.window import ChatWindow
from ui.settings.window import SettingsWindow


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_save_button_only_visible_on_api_page():
    _app()
    window = SettingsWindow()
    save_btn = next(
        button for button in window.findChildren(QPushButton)
        if button.objectName() == "save-config-button"
    )

    window._switch_page(0)
    assert not save_btn.isHidden()

    window._switch_page(1)
    assert save_btn.isHidden()

    window._switch_page(2)
    assert save_btn.isHidden()

    window._switch_page(3)
    assert save_btn.isHidden()

    window._switch_page(4)
    assert save_btn.isHidden()


def test_api_page_discards_unsaved_changes_when_switching_away():
    _app()
    window = SettingsWindow()

    original_model = window._config.api.llm.model
    original_temp = int(window._config.api.llm.temperature * 100)

    window._switch_page(0)
    window._api_page._model.setText("temp-model")
    window._api_page._temp_spin.setValue(123)

    window._switch_page(1)
    window._switch_page(0)

    assert window._api_page._model.text() == original_model
    assert window._api_page._temp_spin.value() == original_temp


class _FakeLLMManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_character(self, *_args, **_kwargs):
        return None


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None


class _FakeSettingsWindow:
    def __init__(self):
        self.show_calls = 0
        self.raise_calls = 0
        self.activate_calls = 0
        self._close_callback = None

    def set_close_callback(self, callback):
        self._close_callback = callback

    def show(self):
        self.show_calls += 1

    def raise_(self):
        self.raise_calls += 1

    def activateWindow(self):
        self.activate_calls += 1

    def close(self):
        if self._close_callback is not None:
            self._close_callback()


def test_chat_window_reuses_existing_settings_window(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    created = []

    def factory():
        window = _FakeSettingsWindow()
        created.append(window)
        return window

    window = ChatWindow(LLMConfig(), settings_window_factory=factory)

    window._open_settings()
    window._open_settings()

    assert len(created) == 1
    assert created[0].show_calls == 2
    assert created[0].raise_calls == 2
    assert created[0].activate_calls == 2


def test_chat_window_recreates_settings_window_after_close(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    created = []

    def factory():
        window = _FakeSettingsWindow()
        created.append(window)
        return window

    window = ChatWindow(LLMConfig(), settings_window_factory=factory)

    window._open_settings()
    created[0].close()
    window._open_settings()

    assert len(created) == 2
