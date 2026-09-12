from __future__ import annotations

from agents.agent_1 import Agent1


class AgentRegistry:
    """Single registry for local agents that Needle is allowed to select."""

    def __init__(self) -> None:
        agent_1 = Agent1()
        self._agents = {agent_1.identifier: agent_1}

    @property
    def tool_definitions(self) -> tuple[tuple[str, str], ...]:
        """Expose the available agents to the decision LLM."""
        return tuple(
            (identifier, agent.description)
            for identifier, agent in self._agents.items()
        )

    def run(self, identifier: str, text: str, language: str) -> str | None:
        """Run an agent selected by Needle, if it is registered."""
        agent = self._agents.get(identifier)
        if agent is None:
            return None
        return agent.run(text=text, language=language)
