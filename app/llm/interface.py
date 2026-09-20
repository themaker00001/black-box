from __future__ import annotations

from abc import ABC, abstractmethod


class LlmError(Exception):
    """Raised when the local LLM backend can't be reached or fails to respond."""


class LlmClient(ABC):
    """Everything above this layer (the debug agent) talks to a model through
    this interface only, so swapping Ollama for another local backend later
    means adding one new class, not touching the agent."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a single-turn request and return the model's text response."""
