from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import QObject, Signal

from backend_support import BackendTestCase
from core.assistant_controller import AssistantController
from core.settings import Settings


class LocalService(QObject):
    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    speechStarted = Signal()
    speechFinished = Signal()
    transcriptionReady = Signal(str)
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(self):
        super().__init__()
        self.installed = self.initialized = True
        for name in ("initialize_async", "download", "set_language", "prepare",
                     "set_active", "set_background", "transcribe", "begin_response",
                     "finish_response", "speak", "cancel_response", "shutdown"):
            setattr(self, name, Mock())


class LanguageService(QObject):
    responseUpdated = Signal(str)
    sentenceReady = Signal(str)
    responseReady = Signal(str)
    errorOccurred = Signal(str)

    def __init__(self):
        super().__init__()
        self.reset, self.respond, self.cancel = Mock(), Mock(), Mock()


class AssistantControllerTests(BackendTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = Settings(directory=Path(directory.name))
        self.tts, self.stt = LocalService(), LocalService()
        self.llm, self.recorder = LanguageService(), Mock(recording=False)
        self.recorder.stop.return_value = Path(directory.name) / "input.wav"
        factories = {"Settings": self.settings, "TTSService": self.tts,
                     "STTService": self.stt, "LLMService": self.llm,
                     "AudioRecorder": self.recorder}
        for name, instance in factories.items():
            patcher = patch(f"core.assistant_controller.{name}", return_value=instance)
            patcher.start()
            self.addCleanup(patcher.stop)
        # Keep language validation real while replacing settings construction.
        self.controller = AssistantController()
        self.addCleanup(self.controller.shutdown)

    def ready(self):
        self.tts.stateChanged.emit("ready")
        self.stt.stateChanged.emit("ready")

    def test_startup_is_serialized_and_idempotent(self):
        self.controller.start()
        self.controller.start()
        self.tts.initialize_async.assert_called_once()
        self.stt.initialize_async.assert_not_called()
        self.tts.stateChanged.emit("loading")
        self.assertTrue(self.controller.modelsLoading)
        self.tts.stateChanged.emit("ready")
        self.stt.initialize_async.assert_called_once()
        self.stt.stateChanged.emit("loading")
        self.stt.stateChanged.emit("ready")
        self.assertTrue(self.controller.modelsReady)
        self.assertFalse(self.controller.modelsLoading)
        self.assertEqual(self.controller.status, "Local models are ready.")
        for service in (self.tts, self.stt):
            service.stateChanged.emit("error")
            self.assertFalse(self.controller.modelsReady)
            service.stateChanged.emit("ready")
            service.stateChanged.emit("not_installed")
            self.assertFalse(self.controller.modelsReady)
            service.stateChanged.emit("ready")

    def test_partial_installation_only_loads_present_models(self):
        for tts, stt in ((True, False), (False, True), (False, False)):
            with self.subTest(tts=tts, stt=stt):
                self.controller._started = False
                self.tts.installed, self.stt.installed = tts, stt
                self.tts.initialize_async.reset_mock()
                self.stt.initialize_async.reset_mock()
                self.controller.start()
                self.assertEqual(self.tts.initialize_async.called, tts)
                self.assertEqual(self.stt.initialize_async.called, stt)
                self.assertEqual(self.controller.ttsInstalled, tts)
                self.assertEqual(self.controller.sttInstalled, stt)

    def test_microphone_to_streamed_reply_and_playback_completion(self):
        self.ready()
        self.controller.startListening()
        self.assertEqual(self.controller.state, "listening")
        self.controller.startListening()
        self.recorder.start.assert_called_once()
        self.controller.stopListening()
        self.stt.transcribe.assert_called_once_with(self.recorder.stop.return_value)
        self.assertEqual(self.controller.state, "thinking")
        self.stt.transcriptionReady.emit("  Hello  ")
        self.assertEqual(self.controller.transcript, "Hello")
        self.tts.begin_response.assert_called_once()
        self.llm.respond.assert_called_once_with("Hello", "en")
        self.llm.responseUpdated.emit("Hi")
        self.llm.sentenceReady.emit("Hi.")
        self.tts.speak.assert_called_once_with("Hi.")
        self.tts.speechStarted.emit()
        self.llm.responseReady.emit("Hi. Welcome!")
        self.assertEqual(self.controller.response, "Hi. Welcome!")
        self.tts.finish_response.assert_called_once()
        self.assertEqual(self.controller.state, "speaking")
        self.tts.speechFinished.emit()
        self.assertEqual(self.controller.state, "idle")
        self.llm.responseUpdated.emit("stale")
        self.llm.sentenceReady.emit("stale")
        self.llm.responseReady.emit("stale")
        self.assertEqual(self.controller.response, "Hi. Welcome!")
        self.assertEqual(self.tts.speak.call_count, 1)

    def test_recording_guards_and_empty_transcription(self):
        self.controller.stopListening()
        self.recorder.stop.assert_not_called()
        self.tts.installed = False
        self.controller.startListening()
        self.tts.installed = True
        self.controller.startListening()
        self.recorder.start.assert_not_called()
        self.ready()
        self.recorder.start.side_effect = RuntimeError("Microphone failed")
        with self.assertLogs("TARS.Assistant", "ERROR"):
            self.controller.startListening()
        self.assertEqual(self.controller.state, "idle")
        self.assertEqual(self.controller.status, "Microphone failed")
        self.recorder.start.side_effect = None
        for failure in (RuntimeError("Too short"), OSError("Disk failed")):
            self.controller.startListening()
            self.recorder.stop.side_effect = failure
            with self.assertLogs("TARS.Assistant"):
                self.controller.stopListening()
            self.assertEqual(self.controller.state, "idle")
            self.stt.transcribe.assert_not_called()
        self.controller._set_state("thinking")
        self.stt.transcriptionReady.emit(" \n ")
        self.assertEqual(self.controller.state, "idle")
        self.llm.respond.assert_not_called()

    def test_errors_cancel_pending_work_and_allow_retry(self):
        for source in (self.llm, self.tts, self.stt):
            with self.subTest(source=source):
                self.controller._set_state("thinking")
                self.controller._response_pending = True
                with self.assertLogs("TARS.Assistant", "ERROR"):
                    source.errorOccurred.emit("Unavailable")
                self.assertEqual(self.controller.state, "idle")
        self.controller._set_state("thinking")
        self.tts.begin_response.side_effect = RuntimeError("Voice busy")
        with self.assertLogs("TARS.Assistant", "ERROR"):
            self.stt.transcriptionReady.emit("Hello")
        self.assertEqual(self.controller.state, "idle")
        self.llm.respond.assert_not_called()
        self.controller._language = "fr"
        with self.assertLogs("TARS.Assistant", "ERROR"):
            self.tts.errorOccurred.emit("Erreur")
            self.stt.errorOccurred.emit("Erreur")
        self.assertIn("Erreur Parakeet", self.controller.status)

    def test_download_queue_completes_only_when_both_models_are_ready(self):
        self.tts.installed = self.stt.installed = False
        self.controller.downloadModels()
        self.controller.downloadModels()
        self.assertTrue(self.controller.modelsDownloading)
        self.tts.download.assert_called_once()
        self.stt.download.assert_not_called()
        self.tts.installed = True
        self.tts.installationFinished.emit()
        self.tts.stateChanged.emit("ready")
        self.stt.download.assert_called_once()
        self.stt.installed = True
        self.stt.installationFinished.emit()
        self.assertTrue(self.controller.modelsDownloading)
        self.stt.stateChanged.emit("ready")
        self.assertFalse(self.controller.modelsDownloading)
        self.assertEqual(self.controller.state, "idle")
        self.controller.downloadModels()
        self.assertEqual(self.tts.download.call_count, 1)

    def test_installed_models_reload_without_downloading_and_failure_resets_queue(self):
        self.tts.initialized = self.stt.initialized = False
        self.controller.downloadModels()
        self.tts.initialize_async.assert_called_once()
        self.stt.initialize_async.assert_called_once()
        self.tts.installed = False
        self.controller.downloadModels()
        self.tts.installationFailed.emit()
        self.assertFalse(self.controller.modelsDownloading)
        self.assertEqual(self.controller.state, "idle")
        self.assertEqual(self.controller._download_queue, [])

    def test_api_key_change_resets_conversation(self):
        self.controller.saveLlmApiKey("test-key")
        self.assertTrue(self.controller.llmKeyConfigured)
        self.assertEqual(self.controller.llmApiKey, "test-key")
        self.llm.reset.assert_called_once()

    def test_language_selection_clears_exchange_and_respects_busy_state(self):
        with patch("core.assistant_controller.Settings.SUPPORTED_LANGUAGES", Settings.SUPPORTED_LANGUAGES):
            self.controller.setLanguage("de")
            self.controller.setLanguage("en")
            self.controller._set_state("listening")
            self.controller.setLanguage("fr")
            self.assertEqual(self.controller.language, "en")
            self.controller._set_state("idle")
            self.controller.setLanguage("fr")
            self.assertEqual(self.controller.language, "fr")
            self.assertEqual(self.settings.language(), "fr")
            self.tts.set_language.assert_called_once_with("fr")
            self.stt.set_language.assert_called_once_with("fr")
            self.tts.installed = False
            self.controller.setLanguage("en")
            self.assertIn("English voice is not installed", self.controller.status)
            self.controller.setLanguage("fr")
            self.assertIn("Voix française", self.controller.status)
            self.tts.set_language.side_effect = RuntimeError("Busy")
            self.controller.setLanguage("en")
            self.assertEqual(self.controller.status, "Busy")

    def test_shutdown_cancels_microphone_even_if_cancellation_fails(self):
        self.recorder.recording = True
        self.recorder.cancel.side_effect = OSError("Device disconnected")
        with self.assertLogs("TARS.Assistant", "ERROR"):
            self.controller.shutdown()
        self.tts.shutdown.assert_called_once()
        self.stt.shutdown.assert_called_once()
        self.recorder.recording = False
