from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from providers.llm.adapter import LLMAdapter
from providers.llm.base import LLMProvider


class LLMService(QObject):
    """Generate GLM answers asynchronously for the Qt controller."""
    responseReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None,
                 provider: LLMProvider | None = None) -> None:
        super().__init__(parent)
        self._provider = provider if provider is not None else LLMAdapter()
        self._history: list[dict[str, str]] = []

    def reset(self) -> None:
        """Clear the recent conversation."""
        self._history.clear()

    def respond(self, text: str, language: str) -> None:
        """Start an asynchronous GLM request."""
        history = self._history.copy()
        threading.Thread(
            target=self._respond_worker,
            args=(text, language, history),
            name="TARS-GLM-Response",
            daemon=True,
        ).start()

    def _respond_worker(self, text: str, language: str, history: list[dict[str, str]]) -> None:
        try:
            answer = self._provider.complete(text, language, history)
        except (RuntimeError, TimeoutError, ValueError) as exc:
            self.errorOccurred.emit(str(exc))
            return
        self._history = (history + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": answer},
        ])[-10:]
        self.responseReady.emit(answer)
