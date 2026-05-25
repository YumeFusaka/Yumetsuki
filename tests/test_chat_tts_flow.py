from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from config.schema import LLMConfig, TTSConfig
from llm.text_processor import ProcessedText
from tts.types import TTSAudioFormat, TTSStreamEvent
from ui.chat.tts_pipeline import TTSSegmentStatus
from ui.chat.window import ChatWindow
from ui.settings.window import SettingsWindow


def _app() -> QApplication:
    app = QApplication.instance()
    return app or QApplication([])


class _FakeLLMManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_character(self, *_args, **_kwargs):
        return None


class _FakeAgentManager:
    def __init__(self, *args, **kwargs):
        pass

    def set_memory_store(self, *_args, **_kwargs):
        return None


class _FakeSpriteManager:
    def __init__(self, *args, **kwargs):
        pass

    def reload(self, *_args, **_kwargs):
        return None

    def load_character(self, *_args, **_kwargs):
        return None

    def set_emotion(self, *_args, **_kwargs):
        return None


@pytest.fixture
def chat_window(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    window = ChatWindow(
        LLMConfig(),
        tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"),
    )
    window._queued_texts = []
    window._played_audio = []
    window._started_segments = []
    monkeypatch.setattr(
        window,
        "_enqueue_tts_segment",
        lambda text: window._queued_texts.append(text),
        raising=False,
    )
    monkeypatch.setattr(
        window,
        "_play_audio_bytes",
        lambda audio: window._played_audio.append(audio),
        raising=False,
    )
    monkeypatch.setattr(
        window,
        "_start_tts_worker",
        lambda utterance_id, segment_id, text: window._started_segments.append((utterance_id, segment_id, text)),
        raising=False,
    )
    yield window
    window.close()


def test_launch_chat_passes_tts_config(monkeypatch):
    _app()
    captured = {}

    class DummyChatWindow:
        def __init__(self, llm_config, **kwargs):
            captured["llm"] = llm_config
            captured["tts"] = kwargs.get("tts_config")

        def show(self):
            return None

        def set_memory_store(self, memory_store):
            return None

    monkeypatch.setattr("ui.settings.window.ChatWindow", DummyChatWindow)
    monkeypatch.setattr("ui.settings.window.PluginHost", lambda *_: SimpleNamespace(load=lambda: None))
    monkeypatch.setattr("ui.settings.window.MCPHost", lambda *_: SimpleNamespace(connect_all=lambda: None))
    monkeypatch.setattr("ui.settings.window.ToolRegistry", lambda **_: SimpleNamespace())

    class DummyLoader:
        def __init__(self, *_args, **_kwargs):
            self.memory_ready = SimpleNamespace(connect=lambda *_: None)
            self.memory_failed = SimpleNamespace(connect=lambda *_: None)

        def start(self):
            return None

    monkeypatch.setattr("ui.settings.window.MemoryLoaderThread", DummyLoader)

    window = SettingsWindow()
    window._launch_chat()

    assert captured["tts"] == window._config.api.tts


def test_chat_window_llm_error_records_system_log(chat_window, monkeypatch):
    recorded = []
    monkeypatch.setattr(
        chat_window,
        "_record_log_event",
        lambda **kwargs: recorded.append(kwargs),
        raising=False,
    )

    chat_window._on_llm_error("Request timed out")

    assert recorded[-1]["event_type"] == "chat.request_failed"
    assert "Request timed out" in recorded[-1]["details"]["error"]


def test_chunked_output_enqueues_sentence_when_period_arrives(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="第一句", emotion=None))
    assert chat_window._queued_texts == []

    chat_window._on_chunk(ProcessedText(clean_text="第一句。第二", emotion=None))
    assert chat_window._queued_texts == ["第一句。"]


def test_comma_does_not_split_sentence(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="你好，世界", emotion=None))
    assert chat_window._queued_texts == []


def test_done_flushes_tail_without_terminal_punctuation(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="没有句号的尾巴", emotion=None))
    chat_window._on_llm_done()
    assert chat_window._queued_texts == ["没有句号的尾巴"]


def test_prefix_mismatch_does_not_reenqueue_already_committed_tts_prefix(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="第一句。第二句", emotion=None))
    assert chat_window._queued_texts == ["第一句。"]

    chat_window._on_chunk(ProcessedText(clean_text="第一句，第二句。第三句。", emotion=None))

    assert chat_window._queued_texts == ["第一句。", "第二句。", "第三句。"]


def test_segment_results_play_in_segment_order(chat_window):
    chat_window._current_utterance_id = 1
    chat_window._next_play_id = 0
    chat_window._segment_results[(1, 1)] = b"second"
    chat_window._segment_results[(1, 0)] = b"first"

    chat_window._drain_ready_audio()

    assert chat_window._played_audio == [b"first", b"second"]


def test_new_user_turn_invalidates_old_tts_results(chat_window):
    old_id = chat_window._current_utterance_id
    chat_window._begin_new_tts_turn()
    new_id = chat_window._current_utterance_id

    chat_window._handle_tts_result(old_id, 0, b"old")
    chat_window._handle_tts_result(new_id, 0, b"new")

    assert chat_window._played_audio == [b"new"]


def test_handle_tts_stream_event_starts_pcm_backend_on_first_chunk(chat_window, monkeypatch):
    starts = []
    chunks = []
    monkeypatch.setattr(
        chat_window,
        "_start_segment_backend",
        lambda key, audio_format: starts.append((key, audio_format.transport)),
        raising=False,
    )
    monkeypatch.setattr(
        chat_window,
        "_append_segment_chunk",
        lambda key, data: chunks.append((key, data)),
        raising=False,
    )

    key = (chat_window._current_utterance_id, 0)
    chat_window._handle_tts_stream_event(
        key[0],
        key[1],
        TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(transport="pcm_stream", sample_rate=32000, channels=1, sample_width=2),
        ),
    )
    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="chunk", data=b"\x00\x01"))

    assert starts == [(key, "pcm_stream")]
    assert chunks == [(key, b"\x00\x01")]


def test_wav_stream_event_uses_shared_audio_player_path(chat_window, monkeypatch):
    starts = []
    monkeypatch.setattr(
        chat_window,
        "_start_segment_backend",
        lambda key, audio_format: starts.append((key, audio_format.transport)),
        raising=False,
    )

    key = (chat_window._current_utterance_id, 0)
    chat_window._handle_tts_stream_event(
        key[0],
        key[1],
        TTSStreamEvent(
            kind="start",
            format=TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0),
        ),
    )
    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="chunk", data=b"wav-bytes"))
    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="end"))

    assert starts == []
    assert chat_window._played_audio == [b"wav-bytes"]


def test_next_segment_waits_until_current_segment_finishes(chat_window):
    key0 = (chat_window._current_utterance_id, 0)
    key1 = (chat_window._current_utterance_id, 1)

    chat_window._segment_states[key0] = "streaming"
    chat_window._segment_states[key1] = "pending"
    chat_window._segment_events[key1] = [TTSStreamEvent(kind="chunk", data=b"later")]

    chat_window._advance_ready_segments()

    assert chat_window._active_segment_key == key0


def test_pcm_failure_before_audio_starts_forces_session_wav(chat_window):
    adapter = chat_window._tts_adapter
    key = (chat_window._current_utterance_id, 0)

    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="error", message="first chunk timeout"))

    assert adapter.get_session_audio_mode() == "wav"


def test_pcm_timeout_marks_segment_failed_and_advances(chat_window):
    key = (chat_window._current_utterance_id, 0)

    chat_window._handle_tts_stream_event(key[0], key[1], TTSStreamEvent(kind="error", message="read timeout"))

    assert chat_window._segment_states[key] == "failed"
    assert chat_window._next_play_id == 1


def test_begin_new_tts_turn_clears_segment_stream_state(chat_window):
    key = (chat_window._current_utterance_id, 0)
    chat_window._segment_states[key] = "streaming"
    chat_window._segment_events[key] = [TTSStreamEvent(kind="chunk", data=b"a")]

    chat_window._begin_new_tts_turn()

    assert chat_window._segment_states == {}
    assert chat_window._segment_events == {}


def test_sentence_segment_is_sent_to_tts_worker(chat_window, monkeypatch):
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._on_chunk(ProcessedText(clean_text="你好。", emotion=None))

    assert chat_window._started_segments == [(chat_window._current_utterance_id, 0, "你好。")]


def test_matching_output_lang_segment_skips_translation(chat_window, monkeypatch):
    chat_window._translation_requests = []
    chat_window._tts_output_lang = "zh"
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )
    monkeypatch.setattr(
        chat_window,
        "_start_translation_worker",
        lambda utterance_id, segment_id, text, target_lang: chat_window._translation_requests.append(
            (utterance_id, segment_id, text, target_lang)
        ),
        raising=False,
    )

    chat_window._enqueue_tts_segment("你好。")

    assert chat_window._translation_requests == []
    assert chat_window._started_segments == [(chat_window._current_utterance_id, 0, "你好。")]


def test_cantonese_output_lang_segment_skips_translation(chat_window, monkeypatch):
    chat_window._translation_requests = []
    chat_window._tts_output_lang = "yue"
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )
    monkeypatch.setattr(
        chat_window,
        "_start_translation_worker",
        lambda utterance_id, segment_id, text, target_lang: chat_window._translation_requests.append(
            (utterance_id, segment_id, text, target_lang)
        ),
        raising=False,
    )

    chat_window._enqueue_tts_segment("你好嗎？")

    assert chat_window._translation_requests == []
    assert chat_window._started_segments == [(chat_window._current_utterance_id, 0, "你好嗎？")]


def test_non_matching_output_lang_segment_translates_before_tts(chat_window, monkeypatch):
    chat_window._translation_requests = []
    chat_window._tts_output_lang = "en"
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )
    monkeypatch.setattr(
        chat_window,
        "_start_translation_worker",
        lambda utterance_id, segment_id, text, target_lang: chat_window._translation_requests.append(
            (utterance_id, segment_id, text, target_lang)
        ),
        raising=False,
    )

    chat_window._enqueue_tts_segment("你好。")

    assert chat_window._translation_requests == [(chat_window._current_utterance_id, 0, "你好。", "en")]
    assert chat_window._started_segments == []


def test_tts_enqueue_queues_translation_when_worker_limit_is_reached(chat_window, monkeypatch):
    chat_window._tts_output_lang = "en"
    chat_window._active_translation_workers = ["busy"]
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("你好。")

    assert chat_window._pending_translation_segments == [
        (chat_window._current_utterance_id, 0, "你好。", "en")
    ]
    assert chat_window._started_segments == []


def test_tts_enqueue_queues_synthesis_when_worker_limit_is_reached(chat_window, monkeypatch):
    chat_window._tts_output_lang = "zh"
    chat_window._active_tts_workers = ["busy", "busy-2"]
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("你好。")

    assert chat_window._pending_tts_segments == [
        (chat_window._current_utterance_id, 0, "你好。")
    ]
    assert chat_window._started_segments == []


def test_tts_enqueue_marks_segment_skipped_when_queue_limit_is_exceeded(chat_window, monkeypatch):
    chat_window._tts_pipeline._queue_limit = 1
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("第一句。")
    chat_window._enqueue_tts_segment("第二句。")

    key = (chat_window._current_utterance_id, 1)
    assert chat_window._tts_pipeline.segments[key].status == TTSSegmentStatus.SKIPPED


def test_translation_result_starts_tts_for_original_segment(chat_window):
    chat_window._handle_translation_result(chat_window._current_utterance_id, 3, "hello.")

    assert chat_window._started_segments == [(chat_window._current_utterance_id, 3, "hello.")]


def test_tts_translation_prompt_marks_phonetic_spans_for_sound_preservation(chat_window):
    captured = {}

    class _FakeAdapter:
        def stream_chat(self, messages, tools=None):
            captured["messages"] = messages
            yield "ややや、"
            yield "やめて。"

    chat_window._llm = SimpleNamespace(_adapter=_FakeAdapter())

    translated = chat_window._translate_tts_text("呀呀呀，不要这样。", "ja")

    assert translated == "ややや、やめて。"
    assert "优先保留发音感觉" in captured["messages"][0]["content"]
    assert "<phonetic>呀呀呀</phonetic>，不要这样。" in captured["messages"][1]["content"]


def test_tts_translation_prompt_does_not_mark_plain_text(chat_window):
    captured = {}

    class _FakeAdapter:
        def stream_chat(self, messages, tools=None):
            captured["messages"] = messages
            yield "hello there."

    chat_window._llm = SimpleNamespace(_adapter=_FakeAdapter())

    translated = chat_window._translate_tts_text("你好，今天怎么样？", "en")

    assert translated == "hello there."
    assert "<phonetic>" not in captured["messages"][1]["content"]


def test_translation_failure_skips_current_segment_and_keeps_following_playable(chat_window):
    chat_window._current_utterance_id = 1
    chat_window._next_play_id = 0

    chat_window._handle_translation_result(chat_window._current_utterance_id, 0, None)
    assert chat_window._played_audio == []

    chat_window._handle_tts_result(chat_window._current_utterance_id, 1, b"next")
    assert chat_window._played_audio == [b"next"]


def test_new_user_turn_invalidates_old_translation_results(chat_window):
    old_id = chat_window._current_utterance_id
    chat_window._begin_new_tts_turn()
    new_id = chat_window._current_utterance_id

    chat_window._handle_translation_result(old_id, 0, "old")
    chat_window._handle_translation_result(new_id, 0, "new")

    assert chat_window._started_segments == [(new_id, 0, "new")]


def test_finished_translation_worker_drains_pending_queue(chat_window, monkeypatch):
    started = []

    class _FakeWorker:
        def deleteLater(self):
            return None

    worker = _FakeWorker()
    chat_window._active_translation_workers = [worker]
    chat_window._pending_translation_segments = [(7, 3, "你好。", "en")]
    monkeypatch.setattr(
        chat_window,
        "_start_translation_worker",
        lambda utterance_id, segment_id, text, target_lang: started.append(
            (utterance_id, segment_id, text, target_lang)
        ),
        raising=False,
    )

    chat_window._on_translation_worker_finished(worker)

    assert started == [(7, 3, "你好。", "en")]


def test_finished_tts_worker_drains_pending_queue(chat_window, monkeypatch):
    started = []

    class _FakeWorker:
        def deleteLater(self):
            return None

    worker = _FakeWorker()
    chat_window._active_tts_workers = [worker]
    chat_window._pending_tts_segments = [(7, 3, "hello.")]
    monkeypatch.setattr(
        chat_window,
        "_start_tts_worker",
        lambda utterance_id, segment_id, text: started.append((utterance_id, segment_id, text)),
        raising=False,
    )

    chat_window._on_tts_worker_finished(worker)

    assert started == [(7, 3, "hello.")]


def test_tts_failure_skips_current_segment_and_keeps_following_playable(chat_window):
    chat_window._current_utterance_id = 1
    chat_window._next_play_id = 0

    chat_window._handle_tts_result(chat_window._current_utterance_id, 0, None)
    assert chat_window._played_audio == []

    chat_window._handle_tts_result(chat_window._current_utterance_id, 1, b"next")
    assert chat_window._played_audio == [b"next"]


def test_play_audio_bytes_uses_player_backend(chat_window, monkeypatch):
    payload = b"fake-audio"
    chat_window._player_payloads = []
    monkeypatch.setattr(
        chat_window,
        "_play_audio_bytes",
        ChatWindow._play_audio_bytes.__get__(chat_window, ChatWindow),
    )
    monkeypatch.setattr(
        chat_window,
        "_start_audio_playback",
        lambda audio: chat_window._player_payloads.append(audio),
        raising=False,
    )

    chat_window._play_audio_bytes(payload)

    assert chat_window._player_payloads == [payload]


def test_chat_window_starts_reference_prepare_when_adapter_requests_it(monkeypatch):
    _app()
    monkeypatch.setattr("ui.chat.window.LLMManager", _FakeLLMManager)
    monkeypatch.setattr("ui.chat.window.AgentManager", _FakeAgentManager)
    monkeypatch.setattr("ui.chat.window.SpriteManager", _FakeSpriteManager)

    class _FakeAdapter:
        def needs_reference_prepare(self):
            return True

    starts = []
    monkeypatch.setattr("ui.chat.window.ChatWindow._create_tts_adapter", staticmethod(lambda *_args: _FakeAdapter()))
    monkeypatch.setattr("ui.chat.window.ChatWindow._start_tts_reference_prepare", lambda self: starts.append(True))

    ChatWindow(LLMConfig(), tts_config=TTSConfig(engine="gptsovits", api_url="http://fake:9880"))

    assert starts == [True]


def test_soft_split_enqueues_long_sentence_before_terminal_punctuation(chat_window):
    chat_window._on_chunk(
        ProcessedText(
            clean_text="今天的天气其实挺舒服的，所以我还是想陪你一起慢慢散步，然后再去买点甜品",
            emotion=None,
        )
    )

    assert chat_window._queued_texts == ["今天的天气其实挺舒服的，所以我还是想陪你一起慢慢散步，"]


def test_translation_segments_use_more_conservative_soft_split_threshold(chat_window):
    chat_window._tts_output_lang = "en"
    chat_window._on_chunk(
        ProcessedText(
            clean_text="今天的天气其实挺舒服的，所以我还是想陪你一起慢慢散步",
            emotion=None,
        )
    )

    assert chat_window._queued_texts == []


def test_tts_segment_text_is_cleaned_before_worker(chat_window, monkeypatch):
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("  你好   呀  ")

    assert chat_window._started_segments == [(chat_window._current_utterance_id, 0, "你好 呀")]


def test_emotion_tag_is_removed_before_tts_worker(chat_window, monkeypatch):
    monkeypatch.setattr(
        chat_window,
        "_enqueue_tts_segment",
        ChatWindow._enqueue_tts_segment.__get__(chat_window, ChatWindow),
    )

    chat_window._enqueue_tts_segment("[emotion:超やばい！]")

    assert chat_window._started_segments == []


def test_streaming_emotion_tag_cleanup_does_not_leave_dirty_pending_buffer(chat_window):
    chat_window._on_chunk(ProcessedText(clean_text="[emotion:超", emotion=None))
    assert chat_window._queued_texts == []

    chat_window._on_chunk(ProcessedText(clean_text="", emotion="超やや！"))
    assert chat_window._queued_texts == []

    chat_window._on_chunk(ProcessedText(clean_text="こんにちは！", emotion="超やや！"))

    assert chat_window._queued_texts == ["こんにちは！"]
