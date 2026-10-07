from __future__ import annotations

import threading
from unittest.mock import Mock, patch

from backend_support import BackendTestCase
from core.stt_service import STTService
from core.tts_service import TTSService


class ServiceLifecycleTests(BackendTestCase):
    def service(self, kind):
        adapter = Mock(installed=True, language="en")
        patcher = patch(f"core.{kind}_service.{kind.upper()}Adapter", return_value=adapter)
        patcher.start()
        self.addCleanup(patcher.stop)
        service = (STTService if kind == "stt" else TTSService)()
        self.addCleanup(service.shutdown)
        return service, adapter

    def test_missing_models_do_not_start_loading(self):
        for kind in ("stt", "tts"):
            with self.subTest(kind=kind):
                service, adapter = self.service(kind)
                adapter.installed = False
                states = []
                service.stateChanged.connect(states.append)
                service.initialize_async()
                self.assertEqual(states, ["not_installed"])
                adapter.initialize.assert_not_called()
                service.prepare()
                self.assertFalse(service._workers)

    def test_failed_initialization_is_retryable_and_does_not_report_ready(self):
        for kind in ("stt", "tts"):
            with self.subTest(kind=kind):
                service, adapter = self.service(kind)
                errors, states = [], []
                service.errorOccurred.connect(errors.append)
                service.stateChanged.connect(states.append)
                adapter.initialize.side_effect = RuntimeError("Bad model")
                with self.assertLogs(f"TARS.{kind.upper()}", "ERROR"):
                    service.initialize_async()
                    self.wait_until(lambda: not service._workers)
                self.assertFalse(service.initialized)
                self.assertFalse(service._initializing)
                self.assertEqual(errors, ["Bad model"])
                self.assertEqual(states[-1], "error")
                adapter.initialize.side_effect = None
                service.initialize_async()
                self.wait_until(lambda: not service._workers)
                self.assertTrue(service.initialized)
                service.initialize_async()
                self.assertEqual(adapter.initialize.call_count, 2)

    def test_download_success_and_failure_emit_completion_and_allow_retry(self):
        for kind in ("stt", "tts"):
            with self.subTest(kind=kind):
                service, adapter = self.service(kind)
                finished, failed, errors = [], [], []
                service.installationFinished.connect(lambda: finished.append(True))
                service.installationFailed.connect(lambda: failed.append(True))
                service.errorOccurred.connect(errors.append)
                adapter.download.side_effect = RuntimeError("Offline")
                with self.assertLogs(f"TARS.{kind.upper()}", "ERROR"):
                    service.download()
                    self.wait_until(lambda: not service._workers)
                self.assertFalse(service._installing)
                self.assertFalse(service.initialized)
                self.assertEqual(failed, [True])
                self.assertEqual(errors, ["Offline"])
                adapter.download.side_effect = lambda **kwargs: kwargs["on_status"]("Downloading")
                service.download()
                self.wait_until(lambda: not service._workers)
                self.assertEqual(finished, [True])
                self.assertTrue(service.initialized)

    def test_loading_and_download_requests_are_deduplicated(self):
        for kind in ("stt", "tts"):
            for operation in ("initialize_async", "download"):
                with self.subTest(kind=kind, operation=operation):
                    service, adapter = self.service(kind)
                    entered, finish = threading.Event(), threading.Event()

                    def blocked(**kwargs):
                        entered.set()
                        if not finish.wait(3):
                            raise RuntimeError("Test timed out")

                    method = adapter.initialize if operation == "initialize_async" else adapter.download
                    method.side_effect = blocked
                    try:
                        getattr(service, operation)()
                        self.assertTrue(entered.wait(2))
                        getattr(service, operation)()
                        method.assert_called_once()
                    finally:
                        finish.set()
                        self.wait_until(lambda: not service._workers)

    def test_prewarm_failure_is_retried_by_the_next_request(self):
        for kind in ("stt", "tts"):
            with self.subTest(kind=kind):
                service, adapter = self.service(kind)
                service._initialized = True
                adapter.initialize.side_effect = RuntimeError("Temporary load failure")
                errors = []
                service.errorOccurred.connect(errors.append)
                with self.assertLogs(f"TARS.{kind.upper()}", "ERROR"):
                    service.prepare()
                    self.wait_until(lambda: not service._workers)
                self.assertTrue(service.initialized)
                self.assertEqual(errors, [])
                adapter.initialize.side_effect = None
                service.prepare()
                self.wait_until(lambda: not service._workers)
                self.assertEqual(adapter.initialize.call_count, 2)

    def test_shutdown_prevents_new_workers_and_is_idempotent(self):
        for kind in ("stt", "tts"):
            with self.subTest(kind=kind):
                service, adapter = self.service(kind)
                service.shutdown()
                service.shutdown()
                service.prepare()
                service.download()
                service.initialize_async()
                service._queue_idle_release(0)
                self.assertFalse(service._workers)
                adapter.initialize.assert_not_called()
                adapter.download.assert_not_called()
                adapter.shutdown.assert_called_once()

    def test_language_and_unavailable_request_guards(self):
        stt, recognizer = self.service("stt")
        with self.assertRaises(ValueError):
            stt.set_language("de")
        errors = []
        stt.errorOccurred.connect(errors.append)
        stt.transcribe(Mock())
        self.assertEqual(len(errors), 1)
        recognizer.transcribe.assert_not_called()
        tts, voice = self.service("tts")
        with self.assertRaises(RuntimeError):
            tts.begin_response()
        tts.set_language("en")
        voice.set_language.assert_not_called()
        tts._speaking = True
        with self.assertRaises(RuntimeError):
            tts.set_language("fr")
        tts.download()
        voice.download.assert_not_called()
        tts._speaking = False
        tts._initialized = True
        tts.set_language("fr")
        voice.set_language.assert_called_once_with("fr")
        self.assertFalse(tts.initialized)
