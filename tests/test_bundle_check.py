from __future__ import annotations

import sys
import tempfile
import wave
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from backend_support import BackendTestCase
from core.bundle_check import _check_synthesis, check_bundle


class BundleCheckTests(BackendTestCase):
    def test_streamed_audio_validation_and_recorder_format(self):
        samples = np.full(480, 0.25, dtype=np.float32).tobytes()
        cases = (([], "no audio"), ([(samples, 0)], "sample rates"),
                 ([(samples, 24000), (samples, 16000)], "sample rates"),
                 ([(b"", 24000)], "invalid audio"),
                 ([(np.array([np.nan], dtype=np.float32).tobytes(), 24000)], "invalid audio"),
                 ([(np.zeros(10, dtype=np.float32).tobytes(), 24000)], "invalid audio"))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "audio.wav"
            for chunks, message in cases:
                with self.subTest(message=message):
                    with self.assertRaisesRegex(RuntimeError, message):
                        _check_synthesis(Mock(generate_stream=Mock(return_value=chunks)), "en", output)
            with patch("builtins.print"):
                _check_synthesis(Mock(generate_stream=Mock(return_value=[(samples, 24000)])), "fr", output)
            with wave.open(str(output)) as audio:
                self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()),
                                 (16000, 1, 2))
                self.assertGreater(audio.getnframes(), 0)

    def run_check(self, *, load_models=False, register_shortcut=False, failure=None):
        voices = []

        class Voice:
            def __init__(self, language):
                self.language = language
                self.installed = failure != "missing_voice"
                self.load, self.shutdown = Mock(), Mock()
                samples = np.full(480, 0.25, dtype=np.float32).tobytes()
                self.generate_stream = Mock(return_value=[(samples, 24000)])
                voices.append(self)

        stt = Mock(installed=failure != "missing_stt")
        stt.transcribe.return_value = "" if failure == "empty_transcript" else "Hello"
        engine = Mock()
        engine.rootObjects.return_value = [] if failure == "qml" else [Mock()]
        if failure == "warnings":
            engine.load.side_effect = lambda *args: engine.warnings.connect.call_args.args[0](["QML warning"])
        shortcut, conflicting = Mock(), Mock()
        conflicting.set_shortcut.side_effect = (
            [RuntimeError("already used"), None] if failure not in {"conflict", "shortcut"}
            else ([None] if failure == "conflict" else [RuntimeError("Registration failed")]))
        assistant, desktop, exporter = Mock(), Mock(), Mock()
        root = Path(__file__).resolve().parents[1]
        with ExitStack() as stack:
            values = {"QApplication": Mock(return_value=self.app),
                      "AssistantController": Mock(return_value=assistant),
                      "DesktopService": Mock(return_value=desktop),
                      "ExportService": Mock(return_value=exporter),
                      "QQmlApplicationEngine": Mock(return_value=engine),
                      "GlobalShortcut": Mock(side_effect=[shortcut, conflicting]),
                      "TTSAdapter": Voice, "PocketTTSProvider": Voice,
                      "ParakeetProvider": Mock(return_value=stt),
                      "resource_directory": Mock(return_value=root if failure != "mascot" else Path("/missing"))}
            for name, value in values.items():
                stack.enter_context(patch(f"core.bundle_check.{name}", value))
            stack.enter_context(patch.dict(sys.modules, {
                "pocket_tts": SimpleNamespace(TTSModel=SimpleNamespace(load_model=None if failure == "pocket_loader" else Mock())),
                "piper": SimpleNamespace(PiperVoice=SimpleNamespace(load=None if failure == "piper_loader" else Mock())),
            }))
            stack.enter_context(patch("builtins.print"))
            if failure:
                with self.assertRaises(RuntimeError):
                    check_bundle(load_models, register_shortcut)
            else:
                self.assertEqual(check_bundle(load_models, register_shortcut), 0)
            assistant.shutdown.assert_called_once()
            desktop.shutdown.assert_called_once()
            exporter.shutdown.assert_called_once()
            engine.deleteLater.assert_called_once()
        return voices, stt, shortcut, conflicting

    def test_import_only_and_full_model_checks(self):
        voices, stt, _, _ = self.run_check()
        self.assertEqual(len(voices), 4)
        stt.load.assert_not_called()
        voices, stt, shortcut, conflicting = self.run_check(load_models=True, register_shortcut=True)
        self.assertEqual(stt.transcribe.call_count, 4)
        stt.shutdown.assert_called_once()
        for voice in voices:
            voice.load.assert_called_once_with(voice.language)
            voice.shutdown.assert_called_once()
        self.assertEqual(conflicting.set_shortcut.call_count, 2)
        self.assertEqual(shortcut.shutdown.call_count, 2)

    def test_failed_checks_always_release_application_services(self):
        for failure in ("qml", "warnings", "mascot", "pocket_loader", "piper_loader",
                        "missing_voice", "missing_stt", "empty_transcript", "conflict", "shortcut"):
            with self.subTest(failure=failure):
                self.run_check(load_models=True, register_shortcut=True, failure=failure)
