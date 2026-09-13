from __future__ import annotations

import re
import unicodedata

from core.responses import ResponseCatalog


class IntentMatcher:
    """Recognize configurable local requests without a language model."""

    INTENT_ORDER = (
        "time",
        "date",
        "identity",
        "wellbeing",
        "help",
        "thanks",
        "acknowledge",
        "greeting",
    )

    def __init__(self, catalog: ResponseCatalog) -> None:
        self._catalog = catalog

    def match(self, text: str) -> str:
        normalized = self._normalize(text)
        if not normalized:
            return "unknown"

        agent = self._match_agent(normalized)
        if agent is not None:
            return agent

        rules = self._catalog.intent_rules()
        for intent in self.INTENT_ORDER:
            if self._matches_rules(normalized, rules.get(intent)):
                return intent
        return "unknown"

    def _match_agent(self, text: str) -> str | None:
        for identifier, rules in self._catalog.agent_rules().items():
            aliases = self._strings(rules.get("aliases"))
            verbs = self._strings(rules.get("verbs"))
            if not self._contains_any_phrase(text, aliases):
                continue
            if any(
                text == normalized_alias
                or text.startswith(f"{normalized_alias} ")
                for alias in aliases
                if (normalized_alias := self._normalize(alias))
            ):
                return identifier
            if any(self._contains_stem(text, verb) for verb in verbs):
                return identifier
        return None

    def _matches_rules(self, text: str, rules: object) -> bool:
        if not isinstance(rules, dict):
            return False
        return (
            self._contains_any_phrase(text, self._strings(rules.get("phrases")))
            or self._contains_any_word(text, self._strings(rules.get("words")))
            or any(
                self._contains_stem(text, stem)
                for stem in self._strings(rules.get("stems"))
            )
            or self._contains_word_group(
                text,
                self._word_groups(rules.get("all_words")),
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
    def _word_groups(value: object) -> tuple[tuple[str, ...], ...]:
        if not isinstance(value, list):
            return ()
        return tuple(
            tuple(item for item in group if isinstance(item, str))
            for group in value
            if isinstance(group, list)
        )

    @staticmethod
    def _contains_any_phrase(text: str, phrases: tuple[str, ...]) -> bool:
        padded_text = f" {text} "
        for phrase in phrases:
            normalized_phrase = IntentMatcher._normalize(phrase)
            if normalized_phrase and f" {normalized_phrase} " in padded_text:
                return True
        return False

    @staticmethod
    def _contains_any_word(text: str, words: tuple[str, ...]) -> bool:
        text_words = set(text.split())
        return any(
            normalized_word in text_words
            for word in words
            if (normalized_word := IntentMatcher._normalize(word))
        )

    @staticmethod
    def _contains_word_group(
        text: str,
        groups: tuple[tuple[str, ...], ...],
    ) -> bool:
        text_words = set(text.split())
        for group in groups:
            normalized_group = tuple(
                normalized_word
                for word in group
                if (normalized_word := IntentMatcher._normalize(word))
            )
            if normalized_group and all(
                word in text_words for word in normalized_group
            ):
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
