from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from config.schema import ASRConfig, LLMConfig, TTSConfig
from stt.types import STTResult
from ui.chat.window import ChatWindow, STTTranscribeWorker


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback, *_args, **_kwargs):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _FakeLLMManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_character(self, *_args, **_kwargs):
        return None


class _FakeLLMWorker:
    instances = []


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_memory_store(self, *_args, **_kwargs):
        return None


class _RecordingLogService:
    def __init__(self):
        self.events = []

    def record(self, event):
        self.events.append(event)


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None

    def set_emotion(self, *_args, **_kwargs):
        return None


class _ManualRecorder(QObject):
    def __init__(self):
        super().__init__()
        self.start_count = 0
        self.stop_count = 0
        self.cancel_count = 0
        self._source = None
        self._device = None

    def start(self):
        self.start_count += 1
        self._source = object()
        self._device = object()

    def stop(self):
        self.stop_count += 1
        self._source = None
        self._device = None

    def cancel(self):
        self.cancel_count += 1
        self._source = None
        self._device = None


class _FakeSTTManager:
    instances = []

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.args = args
        self.kwargs = kwargs
        self.audios = []
        _FakeSTTManager.instances.append(self)

    def transcribe_wav(self, audio):
        self.audios.append(audio)
        return STTResult(text="默认识别")


def _patch_window_dependencies(
    monkeypatch,
    patch_stt_manager=True,
    patch_llm_worker=False,
):
    global _FakeLLMWorker

    _app()
    _FakeSTTManager.instances = []
    _FakeLLMWorker.instances = []

    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    if patch_llm_worker:
        class _QtFakeLLMWorker(QThread):
            chunk_received = Signal(object)
            finished_signal = Signal()
            error_signal = Signal(str)

            instances = []

            def __init__(self, chat_engine, user_input):
                super().__init__()
                self.chat_engine = chat_engine
                self.user_input = user_input
                self.start_count = 0
                _QtFakeLLMWorker.instances.append(self)

            def start(self):
                self.start_count += 1

        _FakeLLMWorker = _QtFakeLLMWorker
        monkeypatch.setattr("ui.chat.window.LLMWorker", _FakeLLMWorker)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)
    if patch_stt_manager:
        monkeypatch.setattr("ui.chat.window.STTManager", _FakeSTTManager)


def _make_window(
    monkeypatch,
    asr_config=None,
    patch_stt_manager=True,
    patch_llm_worker=False,
    log_service=None,
):
    _patch_window_dependencies(
        monkeypatch,
        patch_stt_manager=patch_stt_manager,
        patch_llm_worker=patch_llm_worker,
    )
    window = ChatWindow(
        LLMConfig(),
        tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"),
        asr_config=asr_config or ASRConfig(),
        log_service=log_service,
    )
    return window


def _close_window(window):
    if getattr(window, "_worker", None) is not None:
        window._worker.deleteLater()
        window._worker = None
    if getattr(window, "_stt_worker", None) is not None:
        window._stt_worker.wait(1000)
        window._stt_worker.deleteLater()
        window._stt_worker = None
    if getattr(window, "_stt_recorder", None) is not None:
        window._stt_recorder.deleteLater()
        window._stt_recorder = None
    window.close()
    _FakeSTTManager.instances = []
    _FakeLLMWorker.instances = []


def test_mic_button_disabled_when_stt_engine_is_none(monkeypatch):
    window = _make_window(monkeypatch, ASRConfig(engine="none"), patch_stt_manager=False)
    try:
        assert window._mic_btn.isEnabled() is False
        assert "语音输入未启用" in window._mic_btn.toolTip()
    finally:
        _close_window(window)


def test_stt_success_text_enters_send_path(monkeypatch):
    window = _make_window(monkeypatch, patch_llm_worker=True)
    try:
        window._on_stt_result(STTResult(text="  你好呀  "))

        assert window._input.text() == ""
        assert _FakeLLMWorker.instances[-1].user_input == "你好呀"
        assert _FakeLLMWorker.instances[-1].start_count == 1
        assert window._mic_btn.text() == "🎤"
    finally:
        _close_window(window)


def test_stt_result_after_close_does_not_send(monkeypatch):
    window = _make_window(monkeypatch)
    sends = []
    monkeypatch.setattr(window, "_on_send", lambda: sends.append("send"), raising=False)
    try:
        window.closeEvent(QCloseEvent())
        window._on_stt_result(STTResult(text="关闭后的识别结果"))

        assert sends == []
        assert window._input.text() == ""
    finally:
        _close_window(window)


def test_stt_empty_result_does_not_send(monkeypatch):
    window = _make_window(monkeypatch)
    try:
        window._on_stt_result(STTResult(text="  "))

        assert _FakeLLMWorker.instances == []
        assert window._input.placeholderText() == "没有识别到语音"
    finally:
        _close_window(window)


def test_stt_error_does_not_send(monkeypatch):
    window = _make_window(monkeypatch)
    try:
        window._on_stt_result(STTResult(text="", error="网络失败"))

        assert _FakeLLMWorker.instances == []
        assert "识别失败" in window._input.placeholderText()
    finally:
        _close_window(window)


def test_stt_start_interrupts_current_tts(monkeypatch):
    window = _make_window(monkeypatch)
    calls = []
    monkeypatch.setattr(window, "_begin_new_tts_turn", lambda: calls.append("tts"), raising=False)
    monkeypatch.setattr(window, "_hide_passive_bubble", lambda: calls.append("bubble"), raising=False)

    recorder = _ManualRecorder()
    window._stt_recorder = recorder
    try:
        window._start_stt_recording()

        assert calls == ["bubble", "tts"]
        assert recorder.start_count == 1
        assert window._mic_btn.text() == "×"
        assert window._mic_btn.property("recording") is True
        assert window._input.placeholderText() == "正在听..."
    finally:
        _close_window(window)


def test_stt_start_failure_does_not_interrupt_tts_or_enter_recording_state(monkeypatch):
    window = _make_window(monkeypatch)
    calls = []
    monkeypatch.setattr(window, "_begin_new_tts_turn", lambda: calls.append("tts"), raising=False)
    monkeypatch.setattr(window, "_hide_passive_bubble", lambda: calls.append("bubble"), raising=False)

    class _FailingRecorder(_ManualRecorder):
        def start(self):
            self.start_count += 1

    recorder = _FailingRecorder()
    window._stt_recorder = recorder
    try:
        window._start_stt_recording()

        assert calls == []
        assert recorder.start_count == 1
        assert window._is_stt_recording is False
        assert window._mic_btn.text() == "🎤"
        assert window._input.placeholderText() == "输入消息..."
    finally:
        _close_window(window)


def test_toggle_stt_recording_stops_active_recorder(monkeypatch):
    window = _make_window(monkeypatch)
    recorder = _ManualRecorder()
    window._stt_recorder = recorder
    window._is_stt_recording = True
    window._mic_btn.setText("×")
    window._mic_btn.setToolTip("停止语音输入")
    try:
        window._toggle_stt_recording()

        assert recorder.stop_count == 1
        assert recorder.start_count == 0
        assert window._is_stt_recording is False
        assert window._mic_btn.text() == "🎤"
        assert window._mic_btn.property("recording") is False
        assert window._mic_btn.toolTip() == "语音输入"
    finally:
        _close_window(window)


def test_stt_start_does_not_record_when_llm_worker_is_busy(monkeypatch):
    window = _make_window(monkeypatch)
    recorder = _ManualRecorder()
    window._stt_recorder = recorder
    window._worker = object()
    try:
        window._start_stt_recording()

        assert recorder.start_count == 0
        assert window._is_stt_recording is False
        assert window._mic_btn.text() == "🎤"
        assert window._input.placeholderText() == "输入消息..."
    finally:
        window._worker = None
        _close_window(window)


def test_stt_start_does_not_record_when_stt_worker_is_busy(monkeypatch):
    window = _make_window(monkeypatch)
    recorder = _ManualRecorder()

    class _BusySTTWorker:
        def isRunning(self):
            return True

        def wait(self, timeout):
            return True

        def deleteLater(self):
            return None

    window._stt_recorder = recorder
    window._stt_worker = _BusySTTWorker()
    try:
        window._start_stt_recording()

        assert recorder.start_count == 0
        assert window._is_stt_recording is False
        assert window._mic_btn.text() == "🎤"
        assert window._input.placeholderText() == "输入消息..."
    finally:
        _close_window(window)


def test_close_event_cancels_recorder_and_waits_briefly_for_stt_worker(monkeypatch):
    window = _make_window(monkeypatch)
    recorder = _ManualRecorder()

    class _WaitingSTTWorker:
        def __init__(self):
            self.waits = []

        def wait(self, timeout):
            self.waits.append(timeout)
            return True

        def deleteLater(self):
            return None

    worker = _WaitingSTTWorker()
    window._stt_recorder = recorder
    window._stt_worker = worker
    try:
        window.closeEvent(QCloseEvent())

        assert recorder.cancel_count == 1
        assert worker.waits == [1000]
    finally:
        window._stt_recorder = None
        window._stt_worker = None
        _close_window(window)


def test_llm_logical_done_keeps_worker_until_qthread_finished(monkeypatch):
    window = _make_window(monkeypatch)

    class _Worker:
        def __init__(self):
            self.delete_count = 0

        def deleteLater(self):
            self.delete_count += 1

    worker = _Worker()
    window._worker = worker
    try:
        window._on_llm_done()

        assert window._worker is worker

        window._on_llm_worker_finished(worker)

        assert window._worker is None
        assert worker.delete_count == 1
    finally:
        _close_window(window)


def test_close_event_waits_for_llm_tts_and_translation_workers(monkeypatch):
    window = _make_window(monkeypatch)

    class _WaitingWorker:
        def __init__(self):
            self.waits = []
            self.interrupts = 0

        def requestInterruption(self):
            self.interrupts += 1

        def isRunning(self):
            return True

        def wait(self, timeout):
            self.waits.append(timeout)
            return True

        def deleteLater(self):
            return None

    llm_worker = _WaitingWorker()
    tts_worker = _WaitingWorker()
    translation_worker = _WaitingWorker()
    window._worker = llm_worker
    window._active_tts_workers = [tts_worker]
    window._active_translation_workers = [translation_worker]
    try:
        window.closeEvent(QCloseEvent())

        assert llm_worker.waits == [1000]
        assert tts_worker.waits == [1000]
        assert translation_worker.waits == [1000]
        assert llm_worker.interrupts == 1
        assert tts_worker.interrupts == 1
        assert translation_worker.interrupts == 1
    finally:
        window._worker = None
        window._active_tts_workers = []
        window._active_translation_workers = []
        _close_window(window)


def test_stt_transcribe_worker_calls_manager_with_audio(monkeypatch):
    class _Manager:
        def __init__(self):
            self.audios = []

        def transcribe_wav(self, audio):
            self.audios.append(audio)
            return STTResult(text="同步识别")

    manager = _Manager()
    worker = STTTranscribeWorker(manager, b"fake-wav")
    results = []
    worker.result_ready.connect(results.append)

    worker.run()

    assert manager.audios == [b"fake-wav"]
    assert results == [STTResult(text="同步识别")]


def test_stt_audio_ready_starts_transcribe_worker(monkeypatch):
    log_service = _RecordingLogService()
    window = _make_window(monkeypatch, log_service=log_service)

    class _Worker:
        def __init__(self, audio):
            self.audio = audio
            self.result_ready = _FakeSignal()
            self.finished = _FakeSignal()
            self.start_count = 0
            self.waits = []
            self.delete_count = 0

        def start(self):
            self.start_count += 1

        def isRunning(self):
            return False

        def wait(self, timeout):
            self.waits.append(timeout)
            return True

        def deleteLater(self):
            self.delete_count += 1

    workers = []
    monkeypatch.setattr(
        window,
        "_create_stt_worker",
        lambda audio: workers.append(_Worker(audio)) or workers[-1],
        raising=False,
    )
    try:
        window._on_stt_audio_ready(b"RIFF....WAVE")

        worker = workers[-1]
        assert worker.audio == b"RIFF....WAVE"
        assert worker.start_count == 1
        assert window._stt_worker is worker
        assert window._input.placeholderText() == "正在识别..."
        event_types = [event.event_type for event in log_service.events]
        assert "stt.transcribe_worker_started" in event_types
    finally:
        _close_window(window)


def test_stt_timeout_releases_current_worker_and_logs(monkeypatch):
    log_service = _RecordingLogService()
    config = ASRConfig(transcribe_timeout_seconds=10)
    window = _make_window(monkeypatch, config, log_service=log_service)

    class _Worker:
        result_ready = _FakeSignal()
        finished = _FakeSignal()

        def __init__(self):
            self.interrupted = False
            self.deleted = False

        def isRunning(self):
            return True

        def requestInterruption(self):
            self.interrupted = True

        def quit(self):
            return None

        def deleteLater(self):
            self.deleted = True

    worker = _Worker()
    window._stt_worker = worker
    try:
        window._on_stt_transcribe_timeout(worker)

        assert worker.interrupted is True
        assert window._stt_worker is None
        assert worker in window._expired_stt_workers
        assert "识别超时" in window._input.placeholderText()
        assert any(event.event_type == "stt.transcribe_timeout" for event in log_service.events)
    finally:
        window._expired_stt_workers.clear()
        _close_window(window)


def test_stale_stt_result_is_ignored_and_logged(monkeypatch):
    log_service = _RecordingLogService()
    window = _make_window(monkeypatch, log_service=log_service)
    worker = object()
    try:
        window._on_stt_result_from_worker(worker, STTResult(text="迟到结果"))

        assert window._input.text() == ""
        assert any(event.event_type == "stt.result_ignored" for event in log_service.events)
    finally:
        _close_window(window)


def test_old_stt_worker_finished_does_not_clear_current_worker(monkeypatch):
    window = _make_window(monkeypatch)

    class _Worker:
        def __init__(self, name):
            self.name = name
            self.delete_count = 0
            self.waits = []

        def isRunning(self):
            return False

        def wait(self, timeout):
            self.waits.append(timeout)
            return True

        def deleteLater(self):
            self.delete_count += 1

    old_worker = _Worker("old")
    new_worker = _Worker("new")
    window._stt_worker = new_worker
    try:
        window._on_stt_worker_finished(old_worker)

        assert window._stt_worker is new_worker
        assert old_worker.delete_count == 1
        assert new_worker.delete_count == 0
    finally:
        _close_window(window)
