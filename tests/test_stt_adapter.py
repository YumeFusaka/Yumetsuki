from types import SimpleNamespace

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


def test_openai_whisper_adapter_sends_audio(monkeypatch):
    captured_client = {}
    captured_request = {}

    class _Transcriptions:
        def create(self, **kwargs):
            captured_request.update(kwargs)
            return SimpleNamespace(text=" 你好呀 ")

    class _Audio:
        transcriptions = _Transcriptions()

    class _Client:
        audio = _Audio()

    def fake_openai(**kwargs):
        captured_client.update(kwargs)
        return _Client()

    monkeypatch.setattr("stt.adapters.openai_whisper.OpenAI", fake_openai)

    config = ASRConfig(
        engine="openai_whisper",
        api_key="sk-test",
        base_url="https://api.openai.com/v1",
        model="whisper-1",
        language="zh",
    )
    result = STTManager(config).transcribe_wav(b"RIFF....WAVE")

    assert result == STTResult(text="你好呀", language="zh")
    assert captured_client == {
        "api_key": "sk-test",
        "base_url": "https://api.openai.com/v1",
    }
    assert captured_request["model"] == "whisper-1"
    assert captured_request["language"] == "zh"
    assert captured_request["file"][0] == "speech.wav"
    assert captured_request["file"][2] == "audio/wav"
    assert captured_request["file"][1].read() == b"RIFF....WAVE"


def test_openai_whisper_adapter_returns_error_for_empty_audio(monkeypatch):
    def fail_openai(**kwargs):
        raise AssertionError("空音频不应创建 OpenAI 客户端")

    monkeypatch.setattr("stt.adapters.openai_whisper.OpenAI", fail_openai)

    result = STTManager(ASRConfig(engine="openai_whisper")).transcribe_wav(b"")

    assert result.text == ""
    assert result.error == "录音内容为空"


def test_openai_whisper_adapter_returns_error_for_exception(monkeypatch):
    class _Transcriptions:
        def create(self, **kwargs):
            raise RuntimeError("网络失败")

    class _Audio:
        transcriptions = _Transcriptions()

    class _Client:
        audio = _Audio()

    monkeypatch.setattr("stt.adapters.openai_whisper.OpenAI", lambda **kwargs: _Client())

    result = STTManager(ASRConfig(engine="openai_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert result.error == "网络失败"
