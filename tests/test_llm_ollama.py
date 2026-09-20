from unittest.mock import Mock, patch

import pytest
import requests

from app.config.settings import LlmSettings
from app.llm.interface import LlmError
from app.llm.ollama import OllamaClient


def _settings() -> LlmSettings:
    return LlmSettings(host="http://localhost:11434", model="test-model")


@patch("app.llm.ollama.requests.post")
def test_complete_returns_message_content(mock_post):
    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {"message": {"content": "root cause: disk full"}},
        raise_for_status=lambda: None,
    )

    client = OllamaClient(_settings())
    result = client.complete("system", "user")

    assert result == "root cause: disk full"
    called_url = mock_post.call_args.args[0]
    assert called_url == "http://localhost:11434/api/chat"


@patch("app.llm.ollama.requests.post", side_effect=requests.ConnectionError("refused"))
def test_complete_raises_llm_error_when_unreachable(mock_post):
    client = OllamaClient(_settings())
    with pytest.raises(LlmError):
        client.complete("system", "user")


@patch("app.llm.ollama.requests.post")
def test_complete_raises_on_missing_content(mock_post):
    mock_post.return_value = Mock(status_code=200, json=lambda: {}, raise_for_status=lambda: None)

    client = OllamaClient(_settings())
    with pytest.raises(LlmError):
        client.complete("system", "user")


@patch("app.llm.ollama.requests.get")
def test_list_models_parses_names(mock_get):
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {"models": [{"name": "llama3.2:latest"}, {"name": "qwen3:14b"}]},
        raise_for_status=lambda: None,
    )

    client = OllamaClient(_settings())
    assert client.list_models() == ["llama3.2:latest", "qwen3:14b"]
