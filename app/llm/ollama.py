from __future__ import annotations

import logging

import requests

from app.config.settings import LlmSettings
from app.llm.interface import LlmClient, LlmError

logger = logging.getLogger(__name__)


class OllamaClient(LlmClient):
    """Talks to a local Ollama daemon over its HTTP API. Nothing ever leaves
    the machine: this only ever calls settings.host, which defaults to
    http://localhost:11434."""

    def __init__(self, settings: LlmSettings) -> None:
        self._settings = settings

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        url = f"{self._settings.host.rstrip('/')}/api/chat"
        body = {
            "model": self._settings.model,
            "stream": False,
            "options": {"temperature": self._settings.temperature},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            response = requests.post(url, json=body, timeout=self._settings.request_timeout_seconds)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmError(
                f"Could not reach Ollama at {self._settings.host} (model '{self._settings.model}'). "
                f"Is 'ollama serve' running and is the model pulled? Underlying error: {exc}"
            ) from exc

        data = response.json()
        message = data.get("message", {})
        content = message.get("content")
        if not content:
            raise LlmError(f"Ollama returned an unexpected response shape: {data}")
        return content

    def list_models(self) -> list[str]:
        url = f"{self._settings.host.rstrip('/')}/api/tags"
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise LlmError(f"Could not reach Ollama at {self._settings.host}: {exc}") from exc
        return [m["name"] for m in response.json().get("models", [])]
