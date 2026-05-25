import pytest

from config.schema import ASRConfig
from stt.adapter import STTAdapter
from stt.manager import STTManager
from stt.types import STTResult


def test_stt_result_defaults():
    result = STTResult(text="你好")

    assert result.text == "你好"
    assert result.language == ""
    assert result.confidence == 0.0
    assert result.error == ""


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        STTAdapter()


def test_stt_manager_disabled_returns_empty_result():
    manager = STTManager(ASRConfig(engine="none"))

    result = manager.transcribe_wav(b"RIFF....WAVE")

    assert result == STTResult(text="")


def test_stt_manager_rejects_unknown_engine():
    manager = STTManager(ASRConfig(engine="missing"))

    result = manager.transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert result.error == "不支持的 STT 引擎：missing"


def test_stt_manager_creates_faster_whisper_adapter_by_default():
    manager = STTManager(ASRConfig())

    assert manager._adapter.__class__.__name__ == "FasterWhisperAdapter"


def test_faster_whisper_adapter_sends_wav_to_local_service(monkeypatch):
    captured = {}

    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"text": "  你好呀  ", "language": "zh"}

    def fake_post(url, files=None, data=None, timeout=None):
        captured["url"] = url
        captured["files"] = files
        captured["data"] = data
        captured["timeout"] = timeout
        return _Response()

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", fake_post)

    result = STTManager(
        ASRConfig(
            engine="faster_whisper",
            api_url="http://127.0.0.1:9000/",
            model="small",
            language="auto",
            record_timeout_seconds=15,
        )
    ).transcribe_wav(b"RIFF....WAVE")

    assert captured["url"] == "http://127.0.0.1:9000/transcribe"
    assert captured["data"] == {"model": "small", "language": "auto"}
    assert captured["timeout"] == 25
    assert captured["files"]["file"][0] == "speech.wav"
    assert captured["files"]["file"][2] == "audio/wav"
    assert captured["files"]["file"][1].read() == b"RIFF....WAVE"
    assert result.text == "你好呀"
    assert result.language == "zh"


def test_faster_whisper_adapter_returns_error_for_empty_audio(monkeypatch):
    def fail_post(*_args, **_kwargs):
        raise AssertionError("空音频不应请求本地 STT 服务")

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", fail_post)

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"")

    assert result.text == ""
    assert result.error == "录音内容为空"


def test_faster_whisper_adapter_returns_error_for_invalid_json(monkeypatch):
    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"segments": []}

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", lambda *_args, **_kwargs: _Response())

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "返回格式无效" in result.error


def test_faster_whisper_adapter_returns_error_for_exception(monkeypatch):
    def fail_post(*_args, **_kwargs):
        raise RuntimeError("网络失败")

    monkeypatch.setattr("stt.adapters.faster_whisper.requests.post", fail_post)

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert result.error == "网络失败"


def test_openai_whisper_is_not_supported():
    result = STTManager(ASRConfig(engine="openai_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "不支持的 STT 引擎" in result.error
