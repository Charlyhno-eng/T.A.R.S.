from __future__ import annotations

import json
from collections.abc import Iterator
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


def _request(text: str, language: str, history: list[dict[str, str]],
             config: LLMConfig, *, streaming: bool) -> Request:
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
    body = {
        "model": config.model,
        "messages": messages,
        "max_tokens": config.max_response_tokens,
        "stream": streaming,
    }
    # GLM 5.3 cannot disable thinking; its default effort is max.
    # Keep custom OpenAI-compatible backends free of GLM-specific options.
    if config.model == MODEL:
        body["reasoning_effort"] = "low"
    return Request(
        config.api_url,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )


def complete(text: str, language: str, history: list[dict[str, str]],
             config: LLMConfig | None = None) -> str:
    """Request a GLM answer for the transcript and recent conversation."""
    request = _request(text, language, history, config or LLMConfig(), streaming=False)
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


def stream(text: str, language: str, history: list[dict[str, str]],
           config: LLMConfig | None = None) -> Iterator[str]:
    """Yield spoken content from SSE events, excluding internal reasoning."""
    request = _request(text, language, history, config or LLMConfig(), streaming=True)
    received_content = False
    finished = False
    try:
        with urlopen(request, timeout=60) as response:
            event_lines: list[str] = []
            for raw_line in response:
                line = raw_line.decode("utf-8").rstrip("\r\n")
                if line.startswith("data:"):
                    event_lines.append(line[5:].lstrip())
                if line or not event_lines:
                    continue
                data = "\n".join(event_lines)
                event_lines.clear()
                if data == "[DONE]":
                    finished = True
                    break
                try:
                    event = json.loads(data)
                    if "error" in event:
                        raise RuntimeError("GLM API returned a streaming error.")
                    choices = event.get("choices", [])
                    if not choices:
                        continue  # Usage-only event.
                    choice = choices[0]
                    reason = choice.get("finish_reason")
                    if reason not in (None, "stop", "length"):
                        raise RuntimeError("GLM API interrupted the response.")
                    content = choice.get("delta", {}).get("content")
                    if content is not None and not isinstance(content, str):
                        raise ValueError("Invalid content")
                except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                    raise RuntimeError("GLM API returned an invalid stream.") from exc
                if content:
                    received_content = received_content or bool(content.strip())
                    yield content
                if reason:
                    finished = True
                    break
            if not finished:
                raise RuntimeError("GLM API connection closed before the response finished.")
    except HTTPError as exc:
        raise RuntimeError(f"GLM API returned HTTP {exc.code}.") from exc
    except (URLError, OSError) as exc:
        raise RuntimeError("Unable to connect to the GLM API.") from exc
    except UnicodeError as exc:
        raise RuntimeError("GLM API returned an invalid stream.") from exc
    if not received_content:
        raise RuntimeError("GLM API returned an empty response.")


class GLMProvider:
    """Default HTTP provider; replace this to use another LLM backend."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()

    def complete(self, text: str, language: str, history: list[dict[str, str]]) -> str:
        return complete(text, language, history, self.config)

    def stream(self, text: str, language: str, history: list[dict[str, str]]) -> Iterator[str]:
        return stream(text, language, history, self.config)
