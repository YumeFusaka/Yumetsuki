import pytest
from types import SimpleNamespace

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


def test_faster_whisper_adapter_transcribes_with_local_library(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()
    captured = {}

    class _FakeWhisperModel:
        def __init__(self, model_size_or_path, device=None, compute_type=None, local_files_only=None):
            captured["model_size_or_path"] = model_size_or_path
            captured["device"] = device
            captured["compute_type"] = compute_type
            captured["local_files_only"] = local_files_only

        def transcribe(self, audio, language=None, vad_filter=None, **kwargs):
            captured["audio"] = audio.read()
            captured["language"] = language
            captured["vad_filter"] = vad_filter
            captured["kwargs"] = kwargs
            segments = [SimpleNamespace(text="  你好"), SimpleNamespace(text="呀  ")]
            info = SimpleNamespace(language="zh")
            return segments, info

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)

    result = STTManager(
        ASRConfig(
            engine="faster_whisper",
            model_path=str(model_dir),
            device="cpu",
            compute_type="int8",
            language="auto",
            record_timeout_seconds=15,
        )
    ).transcribe_wav(b"RIFF....WAVE")

    assert captured["model_size_or_path"] == str(model_dir)
    assert captured["device"] == "cpu"
    assert captured["compute_type"] == "int8"
    assert captured["local_files_only"] is True
    assert captured["audio"] == b"RIFF....WAVE"
    assert captured["language"] is None
    assert captured["vad_filter"] is True
    assert captured["kwargs"]["beam_size"] == 1
    assert captured["kwargs"]["best_of"] == 1
    assert captured["kwargs"]["condition_on_previous_text"] is False
    assert result.text == "你好呀"
    assert result.language == "zh"


def test_faster_whisper_adapter_treats_auto_device_as_cpu(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()
    captured = {}

    class _FakeWhisperModel:
        def __init__(self, _model_size_or_path, device=None, **_kwargs):
            captured["device"] = device

        def transcribe(self, *_args, **_kwargs):
            return [SimpleNamespace(text="你好")], SimpleNamespace(language="zh")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)

    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path=str(model_dir), device="auto")
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == "你好"
    assert captured["device"] == "cpu"


def test_faster_whisper_adapter_records_platform_logs(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()

    class _LogService:
        def __init__(self):
            self.events = []

        def record(self, event):
            self.events.append(event)

    class _FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return [SimpleNamespace(text="你好")], SimpleNamespace(language="zh")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)
    log_service = _LogService()

    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path=str(model_dir)),
        log_service=log_service,
        session_id="s1",
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == "你好"
    event_types = [event.event_type for event in log_service.events]
    assert "stt.model_load_started" in event_types
    assert "stt.model_load_completed" in event_types
    assert "stt.transcribe_started" in event_types
    assert "stt.transcribe_completed" in event_types
    assert all(event.session_id == "s1" for event in log_service.events)


def test_faster_whisper_adapter_returns_error_for_empty_audio(monkeypatch):
    def fail_model(*_args, **_kwargs):
        raise AssertionError("空音频不应加载 STT 模型")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", fail_model)

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"")

    assert result.text == ""
    assert result.error == "录音内容为空"


def test_faster_whisper_adapter_returns_error_for_missing_model_path():
    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path="data/models/not-exists")
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "STT 模型目录不存在" in result.error


def test_faster_whisper_adapter_resolves_default_project_model_path(monkeypatch, tmp_path):
    captured = {}
    model_dir = tmp_path / "faster-whisper-large-v3-turbo"
    model_dir.mkdir()

    class _FakeWhisperModel:
        def __init__(self, model_size_or_path, **_kwargs):
            captured["model_size_or_path"] = model_size_or_path

        def transcribe(self, *_args, **_kwargs):
            return [SimpleNamespace(text="你好")], SimpleNamespace(language="zh")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)
    monkeypatch.setattr(
        "stt.adapters.faster_whisper.resolve_model_path",
        lambda path_text, category_dir: captured.setdefault("resolver_args", (path_text, category_dir)) and model_dir,
    )

    result = STTManager(ASRConfig(engine="faster_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == "你好"
    assert captured["resolver_args"][0] == "data/models/stt/faster-whisper-large-v3-turbo"
    assert captured["model_size_or_path"] == str(model_dir)


def test_faster_whisper_adapter_returns_error_for_empty_transcription(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()

    class _FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            return [], SimpleNamespace(language="zh")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)

    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path=str(model_dir))
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "未识别到语音" in result.error


def test_faster_whisper_adapter_returns_error_for_exception(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()

    class _FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def transcribe(self, *_args, **_kwargs):
            raise RuntimeError("识别失败")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)

    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path=str(model_dir))
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert result.error == "识别失败"


def test_faster_whisper_adapter_explains_missing_cuda_runtime(monkeypatch, tmp_path):
    model_dir = tmp_path / "faster-whisper"
    model_dir.mkdir()

    class _FakeWhisperModel:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("Library cublas64_12.dll is not found")

    monkeypatch.setattr("stt.adapters.faster_whisper.WhisperModel", _FakeWhisperModel)

    result = STTManager(
        ASRConfig(engine="faster_whisper", model_path=str(model_dir), device="cuda")
    ).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "CUDA 运行库缺失" in result.error
    assert "设备改为 cpu" in result.error


def test_openai_whisper_is_not_supported():
    result = STTManager(ASRConfig(engine="openai_whisper")).transcribe_wav(b"RIFF....WAVE")

    assert result.text == ""
    assert "不支持的 STT 引擎" in result.error
