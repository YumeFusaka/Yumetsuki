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
