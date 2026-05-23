from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from config.schema import LLMConfig, TTSConfig
from llm.text_processor import ProcessedText
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
    return window


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
