from __future__ import annotations

import os
import tempfile
import threading
import time
import unittest
import weakref
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from core.stt_service import STTService
from core.tts_service import TTSService


class Model:
    pass


class ModelStandbyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, condition) -> None:
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), "Worker did not finish")

    def test_stt_reloads_after_standby_and_releases_weights_even_on_error(self) -> None:
        adapter = Mock(installed=True)
        references = []

        def initialize(**kwargs):
            adapter.model = Model()
            references.append(weakref.ref(adapter.model))

        def release():
            adapter.model = None

        def transcribe(path, language):
            self.assertIsNotNone(adapter.model)
            self.assertEqual(language, "fr")
            if path.name == "failed.wav":
                raise RuntimeError("Inference failed")
            return "Bonjour."

        adapter.initialize.side_effect = initialize
        adapter.transcribe.side_effect = transcribe
        adapter.release_model.side_effect = release
        with patch("core.stt_service.STTAdapter", return_value=adapter), tempfile.TemporaryDirectory() as directory:
            service = STTService(language="fr")
            self.addCleanup(service.shutdown)
            transcripts, errors = [], []
            service.transcriptionReady.connect(transcripts.append)
            service.errorOccurred.connect(errors.append)
            service.initialize_async()
            self.wait_until(lambda: not service._workers)
            self.assertTrue(service.initialized)
            self.assertTrue(all(reference() is None for reference in references))
            for name in ("first.wav", "second.wav", "failed.wav"):
                path = Path(directory) / name
                path.touch()
                service.transcribe(path)
                self.wait_until(lambda: not service._workers)
                self.assertFalse(path.exists())
                self.assertTrue(service.initialized)
                self.assertTrue(all(reference() is None for reference in references))
            self.assertEqual(transcripts, ["Bonjour.", "Bonjour."])
            self.assertEqual(errors, ["Inference failed"])

    def test_hidden_tts_keeps_active_generation_alive_then_reloads_next_reply(self) -> None:
        adapter = Mock(installed=True)
        entered, finish = threading.Event(), threading.Event()
        references = []

        def initialize(**kwargs):
            if adapter.model is None:
                adapter.model = Model()
                references.append(weakref.ref(adapter.model))

        def release():
            adapter.model = None

        def generate(text, stop):
            self.assertIsNotNone(adapter.model)
            entered.set()
            if not finish.wait(3):
                raise RuntimeError("Test timed out")
            self.assertIsNotNone(adapter.model)
            yield b"first", 24000
            yield b"second", 24000

        adapter.model = None
        adapter.initialize.side_effect = initialize
        adapter.shutdown.side_effect = release
        adapter.generate_stream.side_effect = generate
        with patch("core.tts_service.TTSAdapter", return_value=adapter):
            service = TTSService()
            self.addCleanup(service.shutdown)
            audio = []
            with patch.object(service._playback, "begin"), patch.object(
                service._playback, "append", side_effect=lambda pcm, rate: audio.append(pcm)
            ), patch.object(service._playback, "end", side_effect=service._on_playback_finished):
                service.initialize_async()
                self.wait_until(lambda: not service._workers)
                service.begin_response()
                service.speak("Hello.")
                service.finish_response()
                self.assertTrue(entered.wait(2))
                try:
                    service.set_background(True)
                    self.assertIsNotNone(references[0]())
                finally:
                    finish.set()
                self.wait_until(lambda: not service._workers and not service._speaking)
                self.assertTrue(service.initialized)
                self.assertIsNone(references[0]())
                self.assertEqual(audio, [b"first", b"second"])
                service.begin_response()
                service.speak("Another reply.")
                service.finish_response()
                self.wait_until(lambda: not service._workers and not service._speaking)
                self.assertEqual(len(references), 2)
                self.assertTrue(all(reference() is None for reference in references))
                self.assertEqual(audio, [b"first", b"second"] * 2)
                service.set_background(False)
                self.assertTrue(service.initialized)
                self.assertIsNone(adapter.model)  # Reopening does not reload unnecessarily.

    def test_hidden_initialization_and_slow_shutdown_do_not_retain_a_voice(self) -> None:
        for shutdown in (False, True):
            with self.subTest(shutdown=shutdown), patch("core.tts_service.TTSAdapter") as provider:
                adapter = provider.return_value
                adapter.installed = True
                entered, finish = threading.Event(), threading.Event()

                def initialize(**kwargs):
                    entered.set()
                    if not finish.wait(3):
                        raise RuntimeError("Test timed out")

                adapter.initialize.side_effect = initialize
                service = TTSService()
                self.addCleanup(service.shutdown)
                if not shutdown:
                    service.set_background(True)
                    self.wait_until(lambda: not service._workers)
                    adapter.shutdown.reset_mock()
                service.initialize_async()
                self.assertTrue(entered.wait(2))
                worker = next(iter(service._workers))
                try:
                    if shutdown:
                        with patch.object(worker, "join"):
                            service.shutdown()
                    adapter.shutdown.assert_not_called()
                finally:
                    finish.set()
                    self.wait_until(lambda: not service._workers)
                self.assertEqual(service.initialized, not shutdown)
                adapter.shutdown.assert_called_once()
