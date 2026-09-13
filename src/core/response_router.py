from __future__ import annotations

from datetime import datetime

from agents.registry import AgentRegistry
from core.responses import ResponseCatalog


class ResponseRouter:
    """Turn a deterministic route into a local response or an agent call."""

    def __init__(self, catalog: ResponseCatalog, agents: AgentRegistry) -> None:
        self._catalog = catalog
        self._agents = agents

    def respond(self, route: str, text: str, language: str) -> str:
        agent_response = self._agents.run(route, text, language)
        if agent_response is not None:
            return agent_response

        responses = self._catalog.responses(language)
        if route == "time":
            return self._format(
                responses.get("time", ""),
                time=datetime.now().astimezone().strftime("%H:%M"),
            )
        if route == "date":
            return self._format(
                responses.get("date", ""),
                date=datetime.now().astimezone().strftime("%Y-%m-%d"),
            )
        return responses.get(route, responses.get("unknown", ""))

    @staticmethod
    def _format(template: str, **values: str) -> str:
        try:
            return template.format(**values)
        except (KeyError, ValueError):
            return template
