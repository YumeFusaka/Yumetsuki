from __future__ import annotations

import math
import struct
import wave
from io import BytesIO

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


class STTRecorder(QObject):
    audio_ready = Signal(bytes)
    error = Signal(str)

    SAMPLE_RATE = 16000
    CHANNELS = 1
    SAMPLE_WIDTH = 2
    _POLL_INTERVAL_MS = 100

    def __init__(
        self,
        record_timeout_seconds: int,
        silence_threshold: float,
        silence_duration_ms: int,
        initial_silence_grace_ms: int = 3000,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._record_timeout_seconds = max(3, int(record_timeout_seconds))
        self._silence_threshold = max(0.001, float(silence_threshold))
        self._silence_duration_ms = max(300, int(silence_duration_ms))
        self._initial_silence_grace_ms = max(0, int(initial_silence_grace_ms))
        self._source: QAudioSource | None = None
        self._device = None
        self._buffer = bytearray()
        self._silent_ms = 0
        self._stopping = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(self._POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_audio)

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.timeout.connect(self.stop)

    def start(self) -> None:
        if self._source is not None:
            return

        audio_input = QMediaDevices.defaultAudioInput()
        if audio_input.isNull():
            self.error.emit("未找到可用麦克风")
            return

        audio_format = QAudioFormat()
        audio_format.setSampleRate(self.SAMPLE_RATE)
        audio_format.setChannelCount(self.CHANNELS)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        self._buffer.clear()
        self._silent_ms = 0
        self._stopping = False
        self._source = QAudioSource(audio_input, audio_format, self)
        self._device = self._source.start()
        if self._device is None:
            self._release_source()
            self.error.emit("麦克风启动失败")
            return

        self._poll_timer.start()
        self._timeout_timer.start(self._record_timeout_seconds * 1000)

    def stop(self) -> None:
        if self._source is None or self._stopping:
            return

        self._stopping = True
        self._poll_audio()
        self._poll_timer.stop()
        self._timeout_timer.stop()
        self._release_source()
        self.audio_ready.emit(self._build_wav(bytes(self._buffer)))
        self._stopping = False

    def cancel(self) -> None:
        self._poll_timer.stop()
        self._timeout_timer.stop()
        self._release_source()
        self._buffer.clear()
        self._silent_ms = 0
        self._stopping = False

    def _poll_audio(self) -> None:
        if self._device is None:
            return

        chunk = bytes(self._device.readAll())
        if not chunk:
            return

        self._buffer.extend(chunk)
        if self._is_silent(chunk):
            self._silent_ms += self._poll_timer.interval()
        else:
            self._silent_ms = 0

        if (
            not self._stopping
            and self._recorded_ms() >= self._initial_silence_grace_ms
            and self._silent_ms >= self._silence_duration_ms
        ):
            self.stop()

    def _is_silent(self, pcm: bytes) -> bool:
        sample_count = len(pcm) // self.SAMPLE_WIDTH
        if sample_count == 0:
            return True

        usable_length = sample_count * self.SAMPLE_WIDTH
        total = 0
        for offset in range(0, usable_length, self.SAMPLE_WIDTH):
            sample = struct.unpack_from("<h", pcm, offset)[0]
            total += sample * sample

        rms = math.sqrt(total / sample_count) / 32768.0
        return rms < self._silence_threshold

    def _build_wav(self, pcm: bytes) -> bytes:
        output = BytesIO()
        with wave.open(output, "wb") as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(self.SAMPLE_WIDTH)
            wav_file.setframerate(self.SAMPLE_RATE)
            wav_file.writeframes(pcm)
        return output.getvalue()

    def _recorded_ms(self) -> int:
        bytes_per_second = self.SAMPLE_RATE * self.CHANNELS * self.SAMPLE_WIDTH
        if bytes_per_second <= 0:
            return 0
        return int(len(self._buffer) * 1000 / bytes_per_second)

    def _release_source(self) -> None:
        if self._source is not None:
            self._source.stop()
            self._source.deleteLater()
        self._source = None
        self._device = None
