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
    adapter = GPTSoVITSAdapter(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake_audio_data"

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", lambda *a, **kw: mock_resp)

    audio = adapter.synthesize("你好呀")
    assert audio == b"fake_audio_data"


def test_gptsovits_synthesize_failure(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")
    adapter = GPTSoVITSAdapter(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.content = b""

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", lambda *a, **kw: mock_resp)

    audio = adapter.synthesize("你好呀")
    assert audio is None


def test_gptsovits_synthesize_logs_and_returns_none_on_http_error(monkeypatch, capsys):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")
    adapter = GPTSoVITSAdapter(config)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.content = b""

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", lambda *a, **kw: mock_resp)

    assert adapter.synthesize("你好") is None

    captured = capsys.readouterr()
    assert "500" in captured.out


def test_gptsovits_synthesize_uses_tts_endpoint_and_text_lang(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880")
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

    assert adapter.synthesize("你好呀") == b"ok"
    assert captured["url"] == "http://fake:9880/tts"
    assert captured["json"] == {"text": "你好呀", "text_lang": "zh"}


def test_gptsovits_synthesize_uses_output_lang_for_text_lang(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880", output_lang="en")
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

    assert adapter.synthesize("hello") == b"ok"
    assert captured["json"]["text_lang"] == "en"


def test_gptsovits_synthesize_normalizes_output_lang_alias(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880", output_lang="jp")
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

    assert adapter.synthesize("こんにちは") == b"ok"
    assert captured["json"]["text_lang"] == "ja"


def test_gptsovits_synthesize_keeps_explicit_tts_endpoint(monkeypatch):
    config = TTSConfig(engine="gptsovits", api_url="http://fake:9880/tts")
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

    assert adapter.synthesize("你好呀") == b"ok"
    assert captured["url"] == "http://fake:9880/tts"


def test_gptsovits_synthesize_includes_reference_audio_fields_when_configured(monkeypatch):
    config = TTSConfig(
        engine="gptsovits",
        api_url="http://fake:9880",
        ref_audio_path="ref.wav",
        prompt_lang="zh",
        prompt_text="这是参考音频文本",
    )
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

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
    adapter = GPTSoVITSAdapter(config)
    captured = {}

    def fake_post(url, json=None, timeout=None):
        captured["json"] = json
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"ok"
        return mock_resp

    monkeypatch.setattr("tts.adapters.gptsovits.requests.post", fake_post)

    assert adapter.synthesize("こんにちは") == b"ok"
    assert captured["json"]["prompt_lang"] == "ja"
