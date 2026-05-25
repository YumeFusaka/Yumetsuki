import struct
import wave
from io import BytesIO

import ui.chat.stt_recorder as stt_recorder_module
from ui.chat.stt_recorder import STTRecorder


class _FakeTimer:
    def __init__(self, interval=STTRecorder._POLL_INTERVAL_MS):
        self._interval = interval
        self.starts = []
        self.stop_count = 0

    def start(self, *args):
        self.starts.append(args)

    def stop(self):
        self.stop_count += 1

    def interval(self):
        return self._interval


class _FakeAudioInput:
    def __init__(self, is_null=False):
        self._is_null = is_null

    def isNull(self):
        return self._is_null


class _FakeReadDevice:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def readAll(self):
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


class _FakeAudioSource:
    instances = []
    device = None

    def __init__(self, audio_input, audio_format, parent):
        self.audio_input = audio_input
        self.audio_format = audio_format
        self.parent = parent
        self.start_count = 0
        self.stop_count = 0
        self.delete_count = 0
        _FakeAudioSource.instances.append(self)

    def start(self):
        self.start_count += 1
        return _FakeAudioSource.device

    def stop(self):
        self.stop_count += 1

    def deleteLater(self):
        self.delete_count += 1


def _recorder(record_timeout_seconds=20, silence_threshold=0.02, silence_duration_ms=1200):
    recorder = STTRecorder(
        record_timeout_seconds=record_timeout_seconds,
        silence_threshold=silence_threshold,
        silence_duration_ms=silence_duration_ms,
    )
    recorder._poll_timer = _FakeTimer()
    recorder._timeout_timer = _FakeTimer()
    return recorder


def _wav_pcm(wav_bytes):
    with wave.open(BytesIO(wav_bytes), "rb") as wav_file:
        return wav_file.readframes(wav_file.getnframes())


def _patch_audio(monkeypatch, chunks, audio_input=None):
    _FakeAudioSource.instances = []
    _FakeAudioSource.device = _FakeReadDevice(chunks)
    monkeypatch.setattr(stt_recorder_module, "QAudioSource", _FakeAudioSource)
    monkeypatch.setattr(
        stt_recorder_module.QMediaDevices,
        "defaultAudioInput",
        lambda: audio_input or _FakeAudioInput(),
    )


def test_stt_recorder_detects_silence_from_pcm16_samples():
    recorder = STTRecorder(record_timeout_seconds=20, silence_threshold=0.02, silence_duration_ms=1200)

    assert recorder._is_silent(b"\x00\x00" * 1600) is True
    assert recorder._is_silent(struct.pack("<1600h", *([1200] * 1600))) is False


def test_stt_recorder_builds_wav_bytes():
    recorder = STTRecorder(record_timeout_seconds=20, silence_threshold=0.02, silence_duration_ms=1200)
    pcm = struct.pack("<1600h", *([128] * 1600))

    wav = recorder._build_wav(pcm)

    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav[:16]
    with wave.open(BytesIO(wav), "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.readframes(1600) == pcm


def test_stt_recorder_clamps_runtime_settings():
    recorder = STTRecorder(record_timeout_seconds=1, silence_threshold=0, silence_duration_ms=10)

    assert recorder._record_timeout_seconds == 3
    assert recorder._silence_threshold == 0.001
    assert recorder._silence_duration_ms == 300


def test_stt_recorder_start_stop_is_idempotent_and_releases_audio(monkeypatch):
    pcm = struct.pack("<4h", 1, 2, 3, 4)
    _patch_audio(monkeypatch, [pcm])
    recorder = _recorder()
    emitted = []
    recorder.audio_ready.connect(emitted.append)

    recorder.start()
    recorder.start()
    source = _FakeAudioSource.instances[0]
    recorder.stop()
    recorder.stop()

    assert len(_FakeAudioSource.instances) == 1
    assert source.start_count == 1
    assert source.stop_count == 1
    assert source.delete_count == 1
    assert recorder._source is None
    assert recorder._device is None
    assert len(emitted) == 1
    assert _wav_pcm(emitted[0]) == pcm


def test_stt_recorder_cancel_is_safe_and_does_not_emit_audio(monkeypatch):
    _patch_audio(monkeypatch, [struct.pack("<2h", 100, 200)])
    recorder = _recorder()
    emitted = []
    recorder.audio_ready.connect(emitted.append)

    recorder.cancel()
    recorder.start()
    source = _FakeAudioSource.instances[0]
    recorder.cancel()
    recorder.cancel()

    assert emitted == []
    assert source.stop_count == 1
    assert source.delete_count == 1
    assert recorder._source is None
    assert recorder._device is None
    assert recorder._buffer == bytearray()
    assert recorder._silent_ms == 0


def test_stt_recorder_poll_audio_aggregates_chunks():
    first = struct.pack("<2h", 1000, 1000)
    second = struct.pack("<2h", -1000, -1000)
    recorder = _recorder()
    recorder._device = _FakeReadDevice([first, second])

    recorder._poll_audio()
    recorder._poll_audio()

    assert bytes(recorder._buffer) == first + second
    assert recorder._silent_ms == 0


def test_stt_recorder_poll_audio_stops_after_silence_threshold(monkeypatch):
    silent_chunk = b"\x00\x00" * (STTRecorder.SAMPLE_RATE // 10)
    _patch_audio(monkeypatch, [silent_chunk] * 10)
    recorder = _recorder(silence_duration_ms=300)
    emitted = []
    recorder.audio_ready.connect(emitted.append)

    recorder.start()
    for _ in range(10):
        recorder._poll_audio()
        if emitted:
            break

    assert len(emitted) == 1
    assert _wav_pcm(emitted[0]) == silent_chunk * 10
    assert recorder._source is None
    assert recorder._device is None


def test_stt_recorder_pcm16_handles_empty_odd_and_negative_samples():
    recorder = _recorder(silence_threshold=0.02)

    assert recorder._is_silent(b"") is True
    assert recorder._is_silent(struct.pack("<h", 0) + b"\xff") is True
    assert recorder._is_silent(struct.pack("<h", -12000) + b"\x00") is False
