from __future__ import annotations

from dataclasses import dataclass

from agents.registry import AgentRegistry
from core.intent_matcher import IntentMatcher
from core.response_router import ResponseRouter
from core.responses import ResponseCatalog


@dataclass(frozen=True, slots=True)
class InteractionResult:
    """Represent a deterministic answer ready for speech synthesis."""

    response: str
    agent_name: str | None


class InteractionService:
    """Route local user requests without loading a decision model."""

    def __init__(self, response_catalog: ResponseCatalog) -> None:
        self._agents = AgentRegistry()
        self._intent_matcher = IntentMatcher(response_catalog)
        self._responses = ResponseRouter(response_catalog, self._agents)

    def respond(self, text: str, language: str) -> InteractionResult:
        """Resolve a local intent and return its response."""
        route = self._intent_matcher.match(text)
        return InteractionResult(
            response=self._responses.respond(route, text, language),
            agent_name=self._agents.display_name(route),
        )
