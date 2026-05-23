from unittest.mock import patch, MagicMock
from tts.adapter import TTSAdapter
from tts.adapters.gptsovits import GPTSoVITSAdapter
from config.schema import TTSConfig
import pytest


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        TTSAdapter()


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
