from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal


API_URL = "https://api.z.ai/api/paas/v4/chat/completions"
MODEL = "glm-5.3-flash"


def _api_key() -> str:
    key = os.environ.get("ZAI_API_KEY", "").strip()
    if key:
        return key
    env_file = Path(__file__).resolve().parents[2] / ".env"
    try:
        for line in env_file.read_text().splitlines():
            if line.startswith("ZAI_API_KEY="):
                return line.partition("=")[2].strip().strip('"\'')
    except OSError:
        pass
    return ""


def complete(text: str, language: str, history: list[dict[str, str]]) -> str:
    """Request a GLM answer for the transcript and recent conversation."""
    key = _api_key()
    if not key:
        raise RuntimeError("ZAI_API_KEY is missing. Set it in the environment or .env file.")
    messages = [
        {
            "role": "system",
            "content": "You are TARS, a concise voice assistant. Your spoken name is TARS "
            "without periods; always use this short form when referring to yourself in "
            "responses because the text will be read aloud. Reply in "
            + ("French" if language == "fr" else "English")
            + ". Use plain text suitable for speech synthesis.",
        },
        *history[-10:],
        {"role": "user", "content": text},
    ]
    request = Request(
        API_URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": False}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(f"GLM API returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise RuntimeError("Unable to connect to the GLM API.") from exc
    try:
        answer = payload["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError("GLM API returned an invalid response.") from exc
    if not answer:
        raise RuntimeError("GLM API returned an empty response.")
    return answer


class LLMService(QObject):
    """Generate GLM answers asynchronously for the Qt controller."""
    responseReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
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
            answer = complete(text, language, history)
        except (RuntimeError, TimeoutError, ValueError) as exc:
            self.errorOccurred.emit(str(exc))
            return
        self._history = (history + [
            {"role": "user", "content": text},
            {"role": "assistant", "content": answer},
        ])[-10:]
        self.responseReady.emit(answer)
