from unittest.mock import patch, MagicMock
from tts.adapter import TTSAdapter
from tts.adapters.gptsovits import GPTSoVITSAdapter
from tts.types import TTSAudioFormat, TTSStreamEvent
from config.schema import TTSConfig
import pytest


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        TTSAdapter()


def test_tts_audio_format_and_event_store_transport_metadata():
    audio_format = TTSAudioFormat(
        transport="pcm_stream",
        sample_rate=32000,
        channels=1,
        sample_width=2,
    )
    event = TTSStreamEvent(kind="start", format=audio_format)

    assert event.kind == "start"
    assert event.format.transport == "pcm_stream"
    assert event.format.sample_rate == 32000


def test_adapter_synthesize_collects_chunk_bytes_from_stream():
    class _FakeAdapter(TTSAdapter):
        def stream_synthesize(self, text: str):
            yield TTSStreamEvent(
                kind="start",
                format=TTSAudioFormat(transport="wav", sample_rate=0, channels=0, sample_width=0),
            )
            yield TTSStreamEvent(kind="chunk", data=b"abc")
            yield TTSStreamEvent(kind="chunk", data=b"def")
            yield TTSStreamEvent(kind="end")

    assert _FakeAdapter().synthesize("hello") == b"abcdef"


def test_adapter_synthesize_returns_none_on_error_event():
    class _FakeAdapter(TTSAdapter):
        def stream_synthesize(self, text: str):
            yield TTSStreamEvent(kind="error", message="boom")

    assert _FakeAdapter().synthesize("hello") is None


def test_gptsovits_synthesize(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake_audio_data"

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=lambda *a, **kw: mock_resp))
    adapter = GPTSoVITSAdapter(config)

    audio = adapter.synthesize("你好呀")
    assert audio == b"fake_audio_data"


def test_gptsovits_synthesize_failure(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.content = b""
    mock_resp.text = ""

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=lambda *a, **kw: mock_resp))
    adapter = GPTSoVITSAdapter(config)

    audio = adapter.synthesize("你好呀")
    assert audio is None


def test_gptsovits_synthesize_logs_and_returns_none_on_http_error(monkeypatch, capsys):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.content = b""
    mock_resp.text = ""

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=lambda *a, **kw: mock_resp))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("你好") is None

    captured = capsys.readouterr()
    assert "500" in captured.out


def test_gptsovits_synthesize_uses_tts_endpoint_and_text_lang(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("你好呀") == b"ok"
    assert captured["url"] == "http://fake:9880/tts"
    assert captured["json"] == {"text": "你好呀", "text_lang": "zh"}


def test_gptsovits_synthesize_uses_output_lang_for_text_lang(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880", output_lang="en")
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("hello") == b"ok"
    assert captured["json"]["text_lang"] == "en"


def test_gptsovits_synthesize_normalizes_output_lang_alias(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880", output_lang="jp")
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("こんにちは") == b"ok"
    assert captured["json"]["text_lang"] == "ja"


def test_gptsovits_synthesize_keeps_explicit_tts_endpoint(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880/tts")
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("你好呀") == b"ok"
    assert captured["url"] == "http://fake:9880/tts"


def test_gptsovits_synthesize_includes_reference_audio_fields_when_configured(monkeypatch):
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="inline",
        prompt_lang="zh",
        prompt_text="这是参考音频文本",
    )
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("你好呀") == b"ok"
    assert captured["json"] == {
        "text": "你好呀",
        "text_lang": "zh",
        "ref_audio_path": "ref.wav",
        "prompt_lang": "zh",
        "prompt_text": "这是参考音频文本",
    }


def test_gptsovits_synthesize_normalizes_legacy_prompt_lang_alias(monkeypatch):
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        prompt_lang="jp",
        prompt_text="これはサンプルです",
    )
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))
    adapter = GPTSoVITSAdapter(config)

    assert adapter.synthesize("こんにちは") == b"ok"
    assert captured["json"]["prompt_lang"] == "ja"


def test_gptsovits_server_managed_mode_never_sends_reference(monkeypatch):
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: MagicMock(post=fake_post))

    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="server_managed",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    adapter = GPTSoVITSAdapter(config)

    assert adapter.needs_reference_prepare() is False
    assert adapter.synthesize("hello") == b"ok"
    assert captured["json"] == {"text": "hello", "text_lang": "zh"}


def test_gptsovits_session_preload_uses_prepare_endpoint_then_skips_reference(monkeypatch):
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="session_preload",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())

    adapter = GPTSoVITSAdapter(config)
    assert adapter.needs_reference_prepare() is True
    assert adapter.prepare_reference() is True
    assert adapter.synthesize("hello") == b"ok"
    assert calls[0] == ("GET", "http://fake:9880/set_refer_audio", {"refer_audio_path": "ref.wav"})
    assert calls[1][2] == {"text": "hello", "text_lang": "zh"}


def test_gptsovits_auto_mode_falls_back_to_inline_when_prepare_fails(monkeypatch):
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="auto",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 405
            mock_resp.text = "method not allowed"
            return mock_resp

        def post(self, url, json=None, timeout=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())

    adapter = GPTSoVITSAdapter(config)
    assert adapter.prepare_reference() is False
    assert adapter.synthesize("hello") == b"ok"
    assert calls[1][2]["ref_audio_path"] == "ref.wav"


def test_gptsovits_prepared_mode_falls_back_to_inline_when_service_still_requires_reference(monkeypatch):
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="auto",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            if len(calls) == 2:
                mock_resp.status_code = 400
                mock_resp.text = "ref_audio_path is required"
                mock_resp.content = b""
            else:
                mock_resp.status_code = 200
                mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())

    adapter = GPTSoVITSAdapter(config)
    assert adapter.prepare_reference() is True
    assert adapter.synthesize("hello") == b"ok"
    assert calls[1][2] == {"text": "hello", "text_lang": "zh"}
    assert calls[2][2]["prompt_text"] == "参考文本"


def test_gptsovits_synthesize_prepares_reference_before_first_post_when_needed(monkeypatch):
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="session_preload",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())

    adapter = GPTSoVITSAdapter(config)
    assert adapter.synthesize("hello") == b"ok"
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"


def test_gptsovits_auto_mode_caches_inline_requirement_across_adapters(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            if len([item for item in calls if item[0] == "POST"]) == 1:
                mock_resp.status_code = 400
                mock_resp.text = "ref_audio_path is required"
                mock_resp.content = b""
            else:
                mock_resp.status_code = 200
                mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    GPTSoVITSAdapter._REFERENCE_CAPABILITY_CACHE.clear()

    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        reference_mode="auto",
        prompt_lang="zh",
        prompt_text="参考文本",
    )
    first = GPTSoVITSAdapter(config)
    assert first.synthesize("hello") == b"ok"

    second = GPTSoVITSAdapter(config)
    assert second.synthesize("world") == b"ok"

    second_post = [item for item in calls if item[0] == "POST"][-1]
    assert second_post[2]["ref_audio_path"] == "ref.wav"


def test_gptsovits_without_reference_audio_does_not_need_prepare():
    adapter = GPTSoVITSAdapter(TTSConfig(engine="gptsovits", api_url="http://fake:9880"))
    assert adapter.needs_reference_prepare() is False


def test_gptsovits_prepare_reference_sends_session_id(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, *args, **kwargs):
            raise AssertionError("not used")

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(
            engine="gptsovits",
            api_url="http://fake:9880",
            ref_audio_path="ref.wav",
            prompt_lang="zh",
            prompt_text="参考文本",
        ),
        session_id="sess-1",
    )

    adapter.prepare_reference()
    assert calls[0][2]["session_id"] == "sess-1"
    assert calls[0][2]["prompt_lang"] == "zh"
    assert calls[0][2]["prompt_text"] == "参考文本"


def test_gptsovits_prepare_reference_skips_session_extension_when_prompt_metadata_missing(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None, stream=None):
            calls.append(("POST", url, json))
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(
            engine="gptsovits",
            api_url="http://fake:9880",
            ref_audio_path="ref.wav",
            reference_mode="session_preload",
        ),
        session_id="sess-1",
    )

    assert adapter.prepare_reference() is True
    assert calls[0][2] == {"refer_audio_path": "ref.wav"}
    assert adapter.synthesize("hello") == b"ok"
    assert "session_id" not in calls[1][2]


def test_gptsovits_prepare_reference_retries_without_session_id_when_extension_is_rejected(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            calls.append(("GET", url, params))
            mock_resp = MagicMock()
            if len(calls) == 1:
                mock_resp.status_code = 400
                mock_resp.text = "unknown query param session_id"
            else:
                mock_resp.status_code = 200
                mock_resp.text = "ok"
            return mock_resp

        def post(self, *args, **kwargs):
            raise AssertionError("not used")

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(
            engine="gptsovits",
            api_url="http://fake:9880",
            ref_audio_path="ref.wav",
            prompt_lang="zh",
            prompt_text="参考文本",
        ),
        session_id="sess-1",
    )

    assert adapter.prepare_reference() is True
    assert calls[0][2] == {
        "refer_audio_path": "ref.wav",
        "session_id": "sess-1",
        "prompt_lang": "zh",
        "prompt_text": "参考文本",
    }
    assert calls[1][2] == {"refer_audio_path": "ref.wav"}


def test_gptsovits_disables_session_id_for_tts_after_prepare_retry_fallback(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, url, params=None, timeout=None):
            mock_resp = MagicMock()
            if params and "session_id" in params:
                mock_resp.status_code = 400
                mock_resp.text = "unknown query param session_id"
            else:
                mock_resp.status_code = 200
                mock_resp.text = "ok"
            return mock_resp

        def post(self, url, json=None, timeout=None, stream=None):
            calls.append(json)
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(
            engine="gptsovits",
            api_url="http://fake:9880",
            audio_mode="wav",
            ref_audio_path="ref.wav",
            reference_mode="session_preload",
            prompt_lang="zh",
            prompt_text="参考文本",
        ),
        session_id="sess-1",
    )

    assert adapter.prepare_reference() is True
    assert adapter.synthesize("hello") == b"ok"
    assert "session_id" not in calls[0]


def test_gptsovits_retries_tts_without_session_id_when_extension_is_rejected(monkeypatch):
    calls = []

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            calls.append(json)
            mock_resp = MagicMock()
            if len(calls) == 1:
                mock_resp.status_code = 400
                mock_resp.text = "unknown field session_id"
                mock_resp.content = b""
            else:
                mock_resp.status_code = 200
                mock_resp.text = "ok"
                mock_resp.content = b"wav-ok"
            return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(
            engine="gptsovits",
            api_url="http://fake:9880",
            audio_mode="wav",
            ref_audio_path="ref.wav",
            reference_mode="inline",
        ),
        session_id="sess-1",
    )

    assert adapter.synthesize("hello") == b"wav-ok"
    assert calls[0]["session_id"] == "sess-1"
    assert "session_id" not in calls[1]


def test_gptsovits_pcm_stream_mode_uses_low_latency_payload(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200
        headers = {
            "X-Audio-Sample-Rate": "32000",
            "X-Audio-Channels": "1",
            "X-Audio-Sample-Width": "2",
        }

        def iter_content(self, chunk_size=None):
            yield b"\x00\x01"
            yield b"\x02\x03"

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            captured["url"] = url
            captured["json"] = json
            captured["stream"] = stream
            return _FakeResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="pcm_stream"),
        session_id="sess-1",
    )

    events = list(adapter.stream_synthesize("你好"))
    assert captured["json"]["media_type"] == "raw"
    assert captured["json"]["streaming_mode"] == 3
    assert captured["json"]["parallel_infer"] is False
    assert captured["json"]["session_id"] == "sess-1"
    assert captured["stream"] is True
    assert [event.kind for event in events] == ["start", "chunk", "chunk", "end"]


def test_gptsovits_auto_mode_retries_as_wav_and_locks_session(monkeypatch):
    calls = []

    class _FakeRawResponse:
        status_code = 409
        text = "streaming mode unsupported"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeWavResponse:
        status_code = 200
        content = b"wav-bytes"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            calls.append(json)
            return _FakeRawResponse() if len(calls) == 1 else _FakeWavResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="auto"),
        session_id="sess-1",
    )

    assert adapter.synthesize("hello") == b"wav-bytes"
    assert calls[0]["media_type"] == "raw"
    assert calls[1]["media_type"] == "wav"
    assert adapter.get_session_audio_mode() == "wav"


def test_gptsovits_without_session_extension_keeps_original_reference_flow(monkeypatch):
    captured = {}

    class _FakeResponse:
        status_code = 200
        content = b"wav-bytes"
        headers = {}

        def iter_content(self, chunk_size=None):
            return iter(())

    class _FakeSession:
        def get(self, *args, **kwargs):
            raise AssertionError("not used")

        def post(self, url, json=None, timeout=None, stream=None):
            captured["json"] = json
            captured["stream"] = stream
            return _FakeResponse()

    monkeypatch.setattr("tts.adapters.gptsovits.requests.Session", lambda: _FakeSession())
    adapter = GPTSoVITSAdapter(
        TTSConfig(engine="gptsovits", api_url="http://fake:9880", audio_mode="wav", ref_audio_path="ref.wav"),
    )

    assert adapter.synthesize("hello") == b"wav-bytes"
    assert "session_id" not in captured["json"]
    assert captured["json"]["media_type"] == "wav"
    assert captured["json"]["streaming_mode"] == 0
    assert captured["stream"] is False
