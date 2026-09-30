from __future__ import annotations

import io
import json
import os
import unittest
from unittest.mock import patch

from core.llm_service import complete


class LLMServiceTests(unittest.TestCase):
    def test_sends_transcription_and_reads_reply(self) -> None:
        payload = io.BytesIO(b'{"choices":[{"message":{"content":" Hello there. "}}]}')
        with patch.dict(os.environ, {"ZAI_API_KEY": "test-key"}), patch(
            "core.llm_service.urlopen", return_value=payload
        ) as request_mock:
            answer = complete("Hello", "en", [])

        self.assertEqual(answer, "Hello there.")
        request = request_mock.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(body["model"], "glm-5.3-flash")
        system_prompt = body["messages"][0]["content"]
        self.assertIn("You are TARS", system_prompt)
        self.assertIn("without periods", system_prompt)
        self.assertEqual(body["messages"][-1], {"role": "user", "content": "Hello"})
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_empty_reply_fails_without_speech(self) -> None:
        payload = io.BytesIO(b'{"choices":[{"message":{"content":" "}}]}')
        with patch.dict(os.environ, {"ZAI_API_KEY": "test-key"}), patch(
            "core.llm_service.urlopen", return_value=payload
        ):
            with self.assertRaisesRegex(RuntimeError, "empty response"):
                complete("Hello", "en", [])
