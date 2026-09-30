from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.llm_service import LLMConfig, complete
from core.settings import Settings


class LLMServiceTests(unittest.TestCase):
    def test_saved_key_takes_precedence_and_can_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings()
            settings._key_path = Path(directory) / "llm_api_key"
            with patch("core.llm_service.Settings", return_value=settings), patch.dict(
                os.environ, {"ZAI_API_KEY": "environment-key"}
            ), patch("core.llm_service.urlopen", return_value=io.BytesIO(
                b'{"choices":[{"message":{"content":"OK"}}]}'
            )) as request_mock:
                settings.set_llm_api_key(" saved-key ")
                complete("Hello", "en", [], LLMConfig(model="another-model"))
                self.assertEqual(request_mock.call_args.args[0].get_header("Authorization"),
                                 "Bearer saved-key")
                self.assertEqual(json.loads(request_mock.call_args.args[0].data)["model"],
                                 "another-model")
                settings.set_llm_api_key("")
                self.assertEqual(settings.llm_api_key(), "")

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
        self.assertEqual(body["max_tokens"], 160)
        system_prompt = body["messages"][0]["content"]
        self.assertIn("You are TARS", system_prompt)
        self.assertIn("without periods", system_prompt)
        self.assertIn("one or two short sentences", system_prompt)
        self.assertEqual(body["messages"][-1], {"role": "user", "content": "Hello"})
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_empty_reply_fails_without_speech(self) -> None:
        payload = io.BytesIO(b'{"choices":[{"message":{"content":" "}}]}')
        with patch.dict(os.environ, {"ZAI_API_KEY": "test-key"}), patch(
            "core.llm_service.urlopen", return_value=payload
        ):
            with self.assertRaisesRegex(RuntimeError, "empty response"):
                complete("Hello", "en", [])
