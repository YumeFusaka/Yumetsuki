from PySide6.QtWidgets import QApplication

from tts.types import TTSAudioFormat
from ui.chat.audio_backends import StreamingAudioBuffer, WavPlaybackBackend, PcmStreamPlaybackBackend


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


def test_streaming_audio_buffer_reads_appended_bytes_in_order():
    buffer = StreamingAudioBuffer()
    buffer.append_chunk(b"ab")
    buffer.append_chunk(b"cd")

    assert bytes(buffer.readData(4)) == b"abcd"


def test_streaming_audio_buffer_compacts_read_prefix():
    buffer = StreamingAudioBuffer()
    buffer.append_chunk(b"a" * 8192)

    assert bytes(buffer.readData(4096)) == b"a" * 4096

    buffer.append_chunk(b"bc")

    assert buffer._offset < 4096
    assert bytes(buffer.readData(4098)) == b"a" * 4096 + b"bc"
    assert buffer.bytesAvailable() == 0


def test_pcm_backend_marks_audio_as_started_after_first_chunk():
    _app()
    backend = PcmStreamPlaybackBackend()
    backend.start_stream(TTSAudioFormat(transport="pcm_stream", sample_rate=32000, channels=1, sample_width=2))
    backend.append_chunk(b"\x00\x01")

    assert backend.has_started_playback() is True


def test_wav_backend_buffers_whole_audio_until_end():
    _app()
    backend = WavPlaybackBackend()
    backend.start_stream(TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0))
    backend.append_chunk(b"a")
    backend.append_chunk(b"b")
    backend.finish_stream()

    assert backend.current_payload() == b"ab"
