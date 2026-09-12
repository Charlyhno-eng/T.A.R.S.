from __future__ import annotations


class Agent1:
    """Minimal example of a local agent reachable through Needle."""

    identifier = "agent_1"
    description = "Contact the first local demonstration agent."

    def run(self, text: str, language: str) -> str:
        """Handle a request routed to this agent."""
        del text
        if language == "en":
            return "I am indeed Agent 1. You have successfully contacted me."
        return "Je suis bien l’agent 1, vous avez réussi à me contacter."
