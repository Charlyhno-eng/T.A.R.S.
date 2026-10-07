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
from core.model_standby import ModelStandby
from core.assistant_controller import AssistantController


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

    def test_stt_reuses_warm_weights_and_prepares_after_idle_release(self) -> None:
        adapter = Mock(installed=True)
        adapter.model = None
        references = []

        def initialize(**kwargs):
            if adapter.model is None:
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
            self.assertIsNotNone(references[0]())
            for name in ("first.wav", "second.wav"):
                path = Path(directory) / name
                path.touch()
                service.transcribe(path)
                self.wait_until(lambda: not service._workers)
                self.assertFalse(path.exists())
                self.assertTrue(service.initialized)
                self.assertEqual(len(references), 1)
                self.assertIsNotNone(references[0]())
            service._queue_idle_release(service._standby._revision)
            self.wait_until(lambda: not service._workers)
            self.assertIsNone(references[0]())
            self.assertTrue(service.initialized)
            service.prepare()
            self.wait_until(lambda: not service._workers)
            self.assertEqual(len(references), 2)
            path = Path(directory) / "failed.wav"
            path.touch()
            service.transcribe(path)
            self.wait_until(lambda: not service._workers)
            self.assertFalse(path.exists())
            service._queue_idle_release(service._standby._revision)
            self.wait_until(lambda: not service._workers)
            self.assertTrue(all(reference() is None for reference in references))
            self.assertEqual(transcripts, ["Bonjour.", "Bonjour."])
            self.assertEqual(errors, ["Inference failed"])

    def test_hidden_tts_keeps_warm_voice_between_replies_then_expires(self) -> None:
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
                self.assertIsNotNone(references[0]())
                self.assertEqual(audio, [b"first", b"second"])
                service.begin_response()
                service.speak("Another reply.")
                service.finish_response()
                self.wait_until(lambda: not service._workers and not service._speaking)
                self.assertEqual(len(references), 1)
                # Exercise the real delayed cleanup rather than unloading at
                # every sentence/response boundary.
                with patch.object(ModelStandby, "BACKGROUND_IDLE_SECONDS", 0.05):
                    service.set_background(False)
                    service.set_background(True)
                    self.wait_until(lambda: adapter.model is None and not service._workers)
                self.assertTrue(all(reference() is None for reference in references))
                self.assertEqual(audio, [b"first", b"second"] * 2)
                service.set_background(False)
                self.assertTrue(service.initialized)
                service.prepare()
                self.wait_until(lambda: not service._workers)
                self.assertEqual(len(references), 2)
                self.assertIsNotNone(adapter.model)

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
                if not shutdown:
                    adapter.shutdown.assert_not_called()
                    service._queue_idle_release(service._standby._revision)
                    self.wait_until(lambda: not service._workers)
                adapter.shutdown.assert_called_once()

    def test_stale_idle_cleanup_cannot_unload_a_new_request(self) -> None:
        with patch("core.stt_service.STTAdapter") as provider:
            service = STTService()
            self.addCleanup(service.shutdown)
            service.set_background(True)
            revision = service._standby._revision
            # Queue cleanup behind the provider lock, then begin recording.
            with service._provider_lock:
                service._queue_idle_release(revision)
                service.set_active(True)
            self.wait_until(lambda: not service._workers)
            provider.return_value.release_model.assert_not_called()
            service.set_active(False)
            service._queue_idle_release(service._standby._revision)
            self.wait_until(lambda: not service._workers)
            provider.return_value.release_model.assert_called_once()

    def test_idle_deadlines_pause_for_work_and_active_conversations(self) -> None:
        with patch("core.model_standby.threading.Timer") as timer:
            standby = ModelStandby(Mock())
            standby.hold()
            timer.assert_not_called()
            standby.release()
            self.assertEqual(timer.call_args.args[0], 120)
            revision = standby._revision
            self.assertTrue(standby.is_current(revision))
            standby.set_active(True)
            self.assertFalse(standby.is_current(revision))
            timer.return_value.cancel.assert_called_once()
            standby.set_background(True)
            self.assertEqual(timer.call_count, 1)
            standby.set_active(False)
            self.assertEqual(timer.call_args.args[0], 30)
            standby.close()
            self.assertFalse(standby.is_current(standby._revision))

    def test_recording_prewarms_models_and_reply_keeps_idle_cleanup_paused(self) -> None:
        with patch("core.assistant_controller.Settings"), patch(
            "core.assistant_controller.TTSService"
        ) as tts, patch("core.assistant_controller.STTService") as stt, patch(
            "core.assistant_controller.AudioRecorder"
        ) as recorder, patch("core.assistant_controller.LLMService"):
            controller = AssistantController()
            controller._tts_ready = controller._stt_ready = True
            controller.startListening()
            recorder.return_value.start.assert_called_once()
            for service in (tts.return_value, stt.return_value):
                service.set_active.assert_called_once_with(True)
                service.prepare.assert_called_once()
            controller.stopListening()
            self.assertEqual(controller.state, "thinking")
            controller._set_state("speaking")
            for service in (tts.return_value, stt.return_value):
                self.assertTrue(all(call.args == (True,) for call in service.set_active.call_args_list))
            controller._set_state("idle")
            for service in (tts.return_value, stt.return_value):
                service.set_active.assert_called_with(False)
            controller.setWindowVisible(False)
            for service in (tts.return_value, stt.return_value):
                service.set_background.assert_called_once_with(True)
                self.assertEqual(service.prepare.call_count, 1)
            controller.setWindowVisible(True)
            for service in (tts.return_value, stt.return_value):
                service.set_background.assert_called_with(False)
                self.assertEqual(service.prepare.call_count, 2)
