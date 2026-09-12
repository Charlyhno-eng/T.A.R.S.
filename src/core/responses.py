from __future__ import annotations

from pathlib import Path
import tomllib


class ResponseCatalog:
    """Read editable replies and local routing vocabulary."""

    DEFAULT_LANGUAGE = "fr"

    def __init__(self) -> None:
        self._path = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "responses.toml"
        )

    def responses(self, language: str) -> dict[str, str]:
        configured = self._read().get("responses", {})
        if not isinstance(configured, dict):
            return {}
        response_set = configured.get(language)
        if not isinstance(response_set, dict) and language != self.DEFAULT_LANGUAGE:
            response_set = configured.get(self.DEFAULT_LANGUAGE)
        if not isinstance(response_set, dict):
            return {}
        return {
            key: value
            for key, value in response_set.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def intent_rules(self) -> dict[str, dict[str, object]]:
        intents = self._read().get("intents", {})
        if not isinstance(intents, dict):
            return {}
        return {
            identifier: rules
            for identifier, rules in intents.items()
            if isinstance(identifier, str) and isinstance(rules, dict)
        }

    def agent_rules(self) -> dict[str, dict[str, object]]:
        agents = self._read().get("agents", {})
        if not isinstance(agents, dict):
            return {}
        return {
            identifier: rules
            for identifier, rules in agents.items()
            if isinstance(identifier, str) and isinstance(rules, dict)
        }

    def _read(self) -> dict[str, object]:
        try:
            with self._path.open("rb") as response_file:
                data = tomllib.load(response_file)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
