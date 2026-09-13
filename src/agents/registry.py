from __future__ import annotations

from agents.agent_1 import Agent1
from agents.agent_2 import Agent2


class AgentRegistry:
    """Single registry for local agents that T.A.R.S. can contact."""

    def __init__(self) -> None:
        agent_1 = Agent1()
        agent_2 = Agent2()
        self._agents = {
            agent_1.identifier: agent_1,
            agent_2.identifier: agent_2,
        }

    def run(self, identifier: str, text: str, language: str) -> str | None:
        """Run a registered agent when its route is selected."""
        agent = self._agents.get(identifier)
        if agent is None:
            return None
        return agent.run(text=text, language=language)

    def display_name(self, identifier: str) -> str | None:
        """Return the visible name of a registered agent."""
        agent = self._agents.get(identifier)
        if agent is None:
            return None
        return agent.display_name
