from __future__ import annotations

import re
import unicodedata

from core.responses import ResponseCatalog


class IntentMatcher:
    """Recognize configurable local requests before relying on Needle."""

    INTENT_ORDER = (
        "greeting",
        "wellbeing",
        "thanks",
        "help",
        "time",
        "date",
        "identity",
    )

    def __init__(self, catalog: ResponseCatalog) -> None:
        self._catalog = catalog

    def match(self, text: str) -> str | None:
        normalized = self._normalize(text)
        if not normalized:
            return None

        agent = self._match_agent(normalized)
        if agent is not None:
            return agent

        rules = self._catalog.intent_rules()
        for intent in self.INTENT_ORDER:
            if self._matches_rules(normalized, rules.get(intent)):
                return intent
        return None

    def _match_agent(self, text: str) -> str | None:
        for identifier, rules in self._catalog.agent_rules().items():
            aliases = self._strings(rules.get("aliases"))
            verbs = self._strings(rules.get("verbs"))
            if not self._contains_any_phrase(text, aliases):
                continue
            if any(self._contains_stem(text, verb) for verb in verbs):
                return identifier
        return None

    def _matches_rules(self, text: str, rules: object) -> bool:
        if not isinstance(rules, dict):
            return False
        return (
            self._contains_any_phrase(text, self._strings(rules.get("phrases")))
            or any(
                self._contains_stem(text, word)
                for word in self._strings(rules.get("words"))
            )
        )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKD", text).lower()
        normalized = normalized.replace("’", "'").replace("‘", "'")
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])", " ", normalized)
        return re.sub(r"[^a-z0-9]+", " ", normalized).strip()

    @staticmethod
    def _strings(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(item for item in value if isinstance(item, str))

    @staticmethod
    def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
        padded_text = f" {text} "
        for phrase in phrases:
            normalized_phrase = IntentMatcher._normalize(phrase)
            if normalized_phrase and f" {normalized_phrase} " in padded_text:
                return True
        return False

    @staticmethod
    def _contains_stem(text: str, stem: str) -> bool:
        normalized_stem = IntentMatcher._normalize(stem)
        if len(normalized_stem) <= 3:
            return normalized_stem in text.split()
        return any(
            word.startswith(normalized_stem)
            for word in text.split()
            if normalized_stem
        )
