from typing import Protocol


class LLMProvider(Protocol):
    """Interface implemented by response providers."""

    def complete(self, text: str, language: str, history: list[dict[str, str]]) -> str: ...
