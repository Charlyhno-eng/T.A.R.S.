from __future__ import annotations


class Agent1:
    """Minimal example of a local agent reachable through T.A.R.S."""

    identifier = "agent_1"
    display_name = "Agent 1"
    description = "Contact the first local demonstration agent."

    def run(self, text: str, language: str) -> str:
        """Handle a request routed to this agent."""
        del text
        if language == "en":
            return "Agent 1 is connected. How can I help you today?"
        return "L’agent 1 est connecté. Comment puis-je vous aider aujourd’hui ?"
