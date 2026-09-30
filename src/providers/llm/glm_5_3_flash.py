from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.settings import Settings


API_URL = "https://api.z.ai/api/paas/v4/chat/completions"
MODEL = "glm-5.3-flash"
MAX_RESPONSE_TOKENS = 160


@dataclass(frozen=True)
class LLMConfig:
    api_url: str = API_URL
    model: str = MODEL
    max_response_tokens: int = MAX_RESPONSE_TOKENS


def _api_key() -> str:
    return Settings().llm_api_key()


def complete(text: str, language: str, history: list[dict[str, str]],
             config: LLMConfig | None = None) -> str:
    """Request a GLM answer for the transcript and recent conversation."""
    config = config or LLMConfig()
    key = _api_key()
    if not key:
        raise RuntimeError("Z.AI API key is missing. Add it in Settings.")
    messages = [
        {
            "role": "system",
            "content": "You are TARS, a concise voice assistant. Your spoken name is TARS "
            "without periods; always use this short form when referring to yourself in "
            "responses because the text will be read aloud. Answer in one or two "
            "short sentences unless the user explicitly asks for more detail. Reply in "
            + ("French" if language == "fr" else "English")
            + ". Use plain text suitable for speech synthesis.",
        },
        *history[-10:],
        {"role": "user", "content": text},
    ]
    request = Request(
        config.api_url,
        data=json.dumps({
            "model": config.model,
            "messages": messages,
            "max_tokens": config.max_response_tokens,
            "stream": False,
        }).encode(),
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


class GLMProvider:
    """Default HTTP provider; replace this to use another LLM backend."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()

    def complete(self, text: str, language: str, history: list[dict[str, str]]) -> str:
        return complete(text, language, history, self.config)
