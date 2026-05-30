from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QObject, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioOutput, QAudioSink, QMediaDevices, QMediaPlayer

from tts.types import TTSAudioFormat


class StreamingAudioBuffer(QIODevice):
    _COMPACT_THRESHOLD = 4096

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._chunks = bytearray()
        self._offset = 0
        self._finished = False
        self.open(QIODevice.OpenModeFlag.ReadOnly)

    def append_chunk(self, data: bytes) -> None:
        if not data:
            return
        self._compact_if_needed()
        self._chunks.extend(data)
        self.readyRead.emit()

    def finish(self) -> None:
        self._finished = True
        self.readyRead.emit()

    def has_pending_data(self) -> bool:
        return self._offset < len(self._chunks)

    def isSequential(self) -> bool:
        return True

    def atEnd(self) -> bool:
        return self._finished and not self.has_pending_data()

    def bytesAvailable(self) -> int:
        return max(0, len(self._chunks) - self._offset) + super().bytesAvailable()

    def readData(self, maxlen: int):
        if self._offset >= len(self._chunks):
            return b""
        end = min(len(self._chunks), self._offset + maxlen)
        data = bytes(self._chunks[self._offset:end])
        self._offset = end
        self._compact_if_needed()
        return data

    def _compact_if_needed(self) -> None:
        if self._offset < self._COMPACT_THRESHOLD:
            return
        del self._chunks[:self._offset]
        self._offset = 0

    def writeData(self, _data, _length: int) -> int:
        return -1


class WavPlaybackBackend(QObject):
    playback_finished = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._payload = bytearray()
        self._buffer: QBuffer | None = None
        self._is_playing = False

    def start_stream(self, _audio_format: TTSAudioFormat) -> None:
        self.stop()
        self._payload.clear()

    def append_chunk(self, data: bytes) -> None:
        self._payload.extend(data)

    def finish_stream(self) -> None:
        self._release_buffer()
        self._buffer = QBuffer(self)
        self._buffer.setData(QByteArray(bytes(self._payload)))
        self._buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        self._player.setSourceDevice(self._buffer)
        self._is_playing = True
        self._player.play()

    def stop(self) -> None:
        if self._is_playing:
            self._is_playing = False
            self._player.stop()
        self._release_buffer()

    def current_payload(self) -> bytes:
        return bytes(self._payload)

    def _release_buffer(self) -> None:
        if self._buffer is None:
            return
        if self._buffer.isOpen():
            self._buffer.close()
        self._buffer.deleteLater()
        self._buffer = None

    def _on_playback_state_changed(self, state) -> None:
        if state != QMediaPlayer.PlaybackState.StoppedState or not self._is_playing:
            return
        self._is_playing = False
        self._release_buffer()
        self.playback_finished.emit()


class PcmStreamPlaybackBackend(QObject):
    playback_finished = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._buffer: StreamingAudioBuffer | None = None
        self._sink = None
        self._has_started_playback = False
        self._finish_requested = False

    def start_stream(self, audio_format: TTSAudioFormat) -> None:
        self.stop()
        qt_format = QAudioFormat()
        qt_format.setSampleRate(audio_format.sample_rate)
        qt_format.setChannelCount(audio_format.channels)
        qt_format.setSampleFormat(
            QAudioFormat.SampleFormat.Int16
            if audio_format.sample_width == 2
            else QAudioFormat.SampleFormat.UInt8
        )
        self._buffer = StreamingAudioBuffer(self)
        self._sink = self._create_sink(qt_format)
        self._has_started_playback = False
        self._finish_requested = False
        if self._sink is not None and hasattr(self._sink, "stateChanged"):
            self._sink.stateChanged.connect(lambda: self._on_sink_state_changed())
        if self._sink is not None:
            try:
                self._sink.start(self._buffer)
            except Exception:
                self._sink = None

    def append_chunk(self, data: bytes) -> None:
        if self._buffer is None:
            raise RuntimeError("PCM stream not started")
        self._buffer.append_chunk(data)
        if data:
            self._has_started_playback = True

    def finish_stream(self) -> None:
        if self._buffer is None:
            return
        self._finish_requested = True
        self._buffer.finish()
        if self._sink is None or not self._buffer.has_pending_data():
            self.playback_finished.emit()

    def stop(self) -> None:
        if self._sink is not None and hasattr(self._sink, "stop"):
            try:
                self._sink.stop()
            except Exception:
                pass
        self._sink = None
        self._buffer = None
        self._has_started_playback = False
        self._finish_requested = False

    def has_started_playback(self) -> bool:
        return self._has_started_playback

    def _create_sink(self, qt_format: QAudioFormat):
        candidates = []
        try:
            device = QMediaDevices.defaultAudioOutput()
            candidates.extend([
                lambda: QAudioSink(device, qt_format, self),
                lambda: QAudioSink(device, qt_format),
            ])
        except Exception:
            pass
        candidates.extend([
            lambda: QAudioSink(qt_format, self),
            lambda: QAudioSink(qt_format),
        ])
        for factory in candidates:
            try:
                return factory()
            except TypeError:
                continue
            except Exception:
                continue
        return None

    def _on_sink_state_changed(self) -> None:
        if not self._finish_requested or self._buffer is None:
            return
        if self._sink is None or not hasattr(self._sink, "state"):
            return
        state = self._sink.state()
        state_name = getattr(state, "name", str(state))
        if state_name not in {"IdleState", "StoppedState"}:
            return
        if self._buffer.has_pending_data():
            return
        self.playback_finished.emit()
