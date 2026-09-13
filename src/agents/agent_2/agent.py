from __future__ import annotations


class Agent2:
    """Minimal example of a second local agent."""

    identifier = "agent_2"
    display_name = "Agent 2"
    description = "Contact the second local demonstration agent."

    def run(self, text: str, language: str) -> str:
        """Handle a request routed to this agent."""
        del text
        if language == "en":
            return "Agent 2 is connected. What would you like to explore?"
        return "L’agent 2 est connecté. Que souhaitez-vous explorer ?"
