from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.llm_service import LLMService
from providers.llm.glm_5_3_flash import GLMProvider
from providers.stt.adapter import STTAdapter
from providers.tts.adapter import TTSAdapter
from providers.tts.pocket_tts import PocketTTSProvider


class ProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch("providers.tts.piper_tts.resource_directory", return_value=Path(directory.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_local_installation_remains_available_after_restart(self) -> None:
        for adapter in (STTAdapter, TTSAdapter, PocketTTSProvider):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                provider = adapter(data_directory=Path(directory))

                def download_resources(*args, **kwargs) -> None:
                    if isinstance(provider, STTAdapter):
                        provider._model_path.touch()
                    elif isinstance(provider, TTSAdapter):
                        info = provider._language_info("en")
                        for path, size in ((provider._model_path("en"), provider.MODEL_SIZE),
                                           (provider._config_path("en"), info["config_size"])):
                            path.parent.mkdir(parents=True, exist_ok=True)
                            with path.open("wb") as resource:
                                resource.truncate(size)
                    else:
                        for path in (
                            provider._model_path("en"), provider._tokenizer_path("en"),
                            provider._voice_path("en"), provider._config_path("en"),
                        ):
                            path.parent.mkdir(parents=True, exist_ok=True)
                            path.touch()

                self.assertFalse(provider.installed)
                with patch.object(provider, "_download_resources", side_effect=download_resources), patch.object(provider, "load"):
                    provider.download()
                self.assertTrue(provider.installed)
                marker = json.loads(provider._installation_marker.read_text())
                self.assertTrue(marker["offline"])

                restarted = adapter(data_directory=Path(directory))
                self.assertTrue(restarted.installed)
                with patch.object(restarted, "_download_resources") as download, patch.object(restarted, "load") as load:
                    restarted.initialize()
                download.assert_not_called()
                load.assert_called_once()

    def test_failed_loading_does_not_mark_installation_complete(self) -> None:
        for adapter in (STTAdapter, TTSAdapter, PocketTTSProvider):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                provider = adapter(data_directory=Path(directory))
                with (
                    patch.object(provider, "_download_resources"),
                    patch.object(provider, "load", side_effect=RuntimeError("load failed")),
                    patch("providers.tts.pocket_tts.logger.exception"),
                    patch("providers.tts.piper_tts.logger.exception"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "load failed"):
                        provider.download()
                self.assertFalse(provider._installation_marker.exists())
                self.assertFalse(provider.installed)

    def test_uninstalled_providers_cannot_initialize(self) -> None:
        for adapter in (STTAdapter, TTSAdapter, PocketTTSProvider):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                provider = adapter(data_directory=Path(directory))
                with patch.object(provider, "load") as load:
                    with self.assertRaises(RuntimeError):
                        provider.initialize()
                load.assert_not_called()

    def test_voice_switch_releases_model_and_requires_language_resources(self) -> None:
        for adapter in (TTSAdapter, PocketTTSProvider):
            with self.subTest(adapter=adapter), tempfile.TemporaryDirectory() as directory:
                provider = adapter("en", data_directory=Path(directory))
                provider._model = object()
                if isinstance(provider, PocketTTSProvider):
                    provider._voice_state = object()
                with self.assertRaises(ValueError):
                    provider.set_language("de")
                self.assertTrue(provider.initialized)
                provider.set_language("fr")
                self.assertEqual(provider.language, "fr")
                self.assertFalse(provider.initialized)
                self.assertFalse(provider.installed)

    def test_llm_service_routes_to_default_or_injected_provider(self) -> None:
        self.assertIsInstance(LLMService()._provider, GLMProvider)
        provider = Mock(spec=["complete"])
        provider.complete.return_value = "Hello."
        service = LLMService(provider=provider)
        replies = []
        service.responseReady.connect(replies.append)
        service._respond_worker("Hi", "en", [])
        provider.complete.assert_called_once_with("Hi", "en", [])
        self.assertEqual(replies, ["Hello."])
        self.assertEqual(service._history, [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello."},
        ])
