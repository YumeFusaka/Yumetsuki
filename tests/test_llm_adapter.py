from unittest.mock import MagicMock
from llm.adapter import LLMAdapter
from llm.adapters.openai_compat import OpenAICompatAdapter
from config.schema import LLMConfig
import pytest


def test_adapter_is_abstract():
    with pytest.raises(TypeError):
        LLMAdapter()


def test_openai_compat_stream(monkeypatch):
    config = LLMConfig(api_key="test", base_url="http://fake/v1", model="test")

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta.content = "hello"

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter([mock_chunk])

    adapter = OpenAICompatAdapter(config)
    monkeypatch.setattr(adapter, "_client", mock_client)

    messages = [{"role": "user", "content": "hi"}]
    chunks = list(adapter.stream_chat(messages))
    assert chunks == ["hello"]
