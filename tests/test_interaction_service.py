from __future__ import annotations

import unittest

from core.interaction_service import InteractionService
from core.intent_matcher import IntentMatcher
from core.responses import ResponseCatalog
from core.settings import Settings


class IntentMatcherTests(unittest.TestCase):
    """Verify deterministic English and French voice routes."""

    def setUp(self) -> None:
        self.matcher = IntentMatcher(ResponseCatalog())

    def test_recognizes_common_requests(self) -> None:
        cases = {
            "Hi TARS, what time is it?": "time",
            "Bonjour, quelle est la date ?": "date",
            "Who are you?": "identity",
            "Comment vas-tu ?": "wellbeing",
            "Can you help me?": "help",
            "Merci beaucoup": "thanks",
            "D'accord": "acknowledge",
        }
        for request, expected_route in cases.items():
            with self.subTest(request=request):
                self.assertEqual(self.matcher.match(request), expected_route)

    def test_contacts_registered_agents(self) -> None:
        cases = {
            "Please contact Agent 1": "agent_1",
            "Lance l'agent deux": "agent_2",
            "Agent 2": "agent_2",
            "Agent 1, what can you do?": "agent_1",
        }
        for request, expected_route in cases.items():
            with self.subTest(request=request):
                self.assertEqual(self.matcher.match(request), expected_route)


class InteractionServiceTests(unittest.TestCase):
    """Verify agent sessions are exposed to the interface."""

    def test_agent_response_exposes_its_visible_name(self) -> None:
        service = InteractionService(ResponseCatalog())

        result = service.respond("Contact Agent 2", "en")

        self.assertEqual(result.agent_name, "Agent 2")
        self.assertIn("connected", result.response.lower())

    def test_english_is_the_default_language(self) -> None:
        self.assertEqual(Settings.DEFAULT_LANGUAGE, "en")
