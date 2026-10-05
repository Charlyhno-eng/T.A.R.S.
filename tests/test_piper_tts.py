from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import time
import unittest
import wave
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from providers.tts.adapter import TTSAdapter
from providers.tts.piper_tts import PiperTTSProvider


class PiperTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.provider = PiperTTSProvider(data_directory=Path(directory.name))
        # Small fixture files exercise the real integrity checks and installation flow.
        languages = deepcopy(PiperTTSProvider.LANGUAGES)
        for info in languages.values():
            info.update(config_size=2, model_md5=hashlib.md5(b"onnx").hexdigest(),
                        config_md5=hashlib.md5(b"{}").hexdigest())
        self.languages = languages
        for name, value in (("MODEL_SIZE", 4), ("LANGUAGES", languages)):
            patcher = patch.object(PiperTTSProvider, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def download_file(self, *, filename: str, local_dir: str, **kwargs) -> str:
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"{}" if filename.endswith(".json") else b"onnx")
        return str(path)

    def test_default_adapter_uses_piper(self) -> None:
        self.assertIs(TTSAdapter, PiperTTSProvider)
        with self.assertRaises(ValueError):
            PiperTTSProvider("de")

    def test_downloads_selected_voice_and_retains_both_languages_and_pocket(self) -> None:
        pocket_file = self.provider._data_directory / "pocket_tts_installed.json"
        pocket_file.write_text("existing Pocket installation")
        with patch("huggingface_hub.hf_hub_download", side_effect=self.download_file) as download, patch(
            "piper.PiperVoice.load", return_value=Mock()
        ) as load:
            for language in ("en", "fr"):
                self.provider.set_language(language)
                self.assertFalse(self.provider.installed)
                statuses = []
                self.provider.download(statuses.append)
                self.assertTrue(self.provider.installed)
                self.assertTrue(self.provider.initialized)
                self.assertIn("Moteur vocal installé et disponible hors ligne.", statuses)
            self.assertEqual(download.call_count, 4)
            for call, language in zip(download.call_args_list, ("en", "en", "fr", "fr")):
                self.assertEqual(call.kwargs["repo_id"], self.provider.PUBLIC_REPOSITORY)
                self.assertEqual(call.kwargs["revision"], self.provider.VOICES_REVISION)
                self.assertIn(self.languages[language]["voice"], call.kwargs["filename"])
            self.assertFalse(load.call_args.kwargs["use_cuda"])
        self.assertEqual(pocket_file.read_text(), "existing Pocket installation")
        self.provider.set_language("en")
        self.assertTrue(self.provider.installed)
        with patch("huggingface_hub.hf_hub_download", side_effect=AssertionError("network")), patch(
            "piper.PiperVoice.load", return_value=Mock()
        ) as load:
            restarted = PiperTTSProvider(data_directory=self.provider._data_directory)
            restarted.initialize()
            restarted.initialize()
            load.assert_called_once()

    def test_repairs_corrupt_files_and_rejects_incomplete_download(self) -> None:
        model = self.provider._model_path("en")
        model.parent.mkdir(parents=True)
        model.write_bytes(b"junk")
        with patch("huggingface_hub.hf_hub_download", side_effect=self.download_file) as download, patch(
            "piper.PiperVoice.load", return_value=Mock()
        ):
            self.provider.download()
            self.assertTrue(download.call_args_list[0].kwargs["force_download"])
        model.write_bytes(b"x")
        self.assertFalse(self.provider.installed)
        with patch("piper.PiperVoice.load") as load:
            with self.assertRaises(RuntimeError):
                self.provider.initialize()
            load.assert_not_called()
        self.provider._installation_marker.unlink()
        with patch("huggingface_hub.hf_hub_download"), patch("providers.tts.piper_tts.logger.exception"):
            with self.assertRaisesRegex(RuntimeError, "corrompus"):
                self.provider.download()
        self.assertFalse(self.provider._installation_marker.exists())
        self.assertFalse(self.provider.initialized)

    def test_stream_yields_float32_mono_and_stops_before_next_inference(self) -> None:
        model = Mock()
        self.provider._model = model
        audio = np.array([-0.5, 0.0, 0.5], dtype=np.float64)
        chunk = SimpleNamespace(sample_channels=1, sample_rate=22050, audio_float_array=audio)
        produced = []

        def synthesize(text, syn_config=None):
            produced.append(text)
            yield chunk
            produced.append("second inference")
            yield chunk

        model.synthesize.side_effect = synthesize
        stop = threading.Event()
        synthesis_config = SimpleNamespace()
        with patch("piper.SynthesisConfig", return_value=synthesis_config) as config:
            stream = self.provider.generate_stream("  Bonjour.  ", stop)
            pcm, rate = next(stream)
        config.assert_called_once_with(**PiperTTSProvider.SYNTHESIS_SETTINGS)
        self.assertIs(model.synthesize.call_args.kwargs["syn_config"], synthesis_config)
        np.testing.assert_array_equal(np.frombuffer(pcm, dtype=np.float32), audio)
        self.assertEqual(rate, 22050)
        stop.set()
        self.assertEqual(list(stream), [])
        self.assertEqual(produced, ["Bonjour."])
        self.assertEqual(list(self.provider.generate_stream("Hello.", stop)), [])
        self.assertEqual(list(self.provider.generate_stream("  ", threading.Event())), [])
        model.synthesize.assert_called_once()
        self.provider.shutdown()
        with self.assertRaises(RuntimeError):
            list(self.provider.generate_stream("Hello.", threading.Event()))


@unittest.skipUnless(os.environ.get("TARS_TEST_PIPER") == "1",
                     "Set TARS_TEST_PIPER=1 to download and synthesize real EN/FR voices")
class RealPiperTests(unittest.TestCase):
    def check_service_playback(self, provider: PiperTTSProvider, text: str) -> None:
        """Exercise the real synthesis worker and Qt signals with a simulated speaker."""
        from core.audio_playback import QtAudio
        from core.tts_service import TTSService
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtMultimedia import QAudioFormat

        audio_format = QAudioFormat()
        audio_format.setSampleRate(48000)
        audio_format.setChannelCount(2)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        written = []
        with patch("core.tts_service.TTSAdapter", return_value=provider), patch(
            "core.audio_playback.QMediaDevices.defaultAudioOutput"
        ) as output, patch("core.audio_playback.QAudioSink") as sink_class:
            output.return_value.isNull.return_value = False
            output.return_value.isFormatSupported.return_value = False
            output.return_value.preferredFormat.return_value = audio_format
            sink = sink_class.return_value
            sink.format.return_value = audio_format
            sink.state.return_value = QtAudio.State.IdleState
            sink.bytesFree.return_value = 4800
            sink.processedUSecs.return_value = 60_000_000

            def write(pcm):
                written.append(bytes(pcm))
                return len(pcm)

            sink.start.return_value.write.side_effect = write
            service = TTSService(language=provider.language)
            started, finished, errors = [], [], []
            service.speechStarted.connect(lambda: started.append(True))
            service.speechFinished.connect(lambda: finished.append(True))
            service.errorOccurred.connect(errors.append)
            try:
                service._initialize_worker()
                self.assertTrue(service.initialized)
                service.begin_response()
                service.speak(text)
                service.finish_response()
                deadline = time.monotonic() + 10
                while not finished and not errors and time.monotonic() < deadline:
                    QCoreApplication.processEvents()
                    time.sleep(0.005)
                self.assertEqual(errors, [])
                self.assertEqual(started, [True])
                self.assertEqual(finished, [True])
                self.assertFalse(service._speaking)
                pcm = b"".join(written)
                self.assertGreater(len(pcm), 48000 * audio_format.bytesPerFrame())
                self.assertTrue(np.any(np.frombuffer(pcm, dtype=np.int16)))
            finally:
                service.shutdown()

    def test_download_wav_stream_and_offline_restart_in_both_languages(self) -> None:
        from core.audio_playback import AudioPlayback
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtMultimedia import QAudioFormat

        app = QCoreApplication.instance() or QCoreApplication([])
        with tempfile.TemporaryDirectory(prefix="tars-piper-test-") as directory:
            root = Path(directory)
            provider = PiperTTSProvider(data_directory=root)
            for language in ("en", "fr"):
                provider.set_language(language)
                provider.download()
                self.assertTrue(provider.installed)
            provider.shutdown()
            with patch("huggingface_hub.hf_hub_download", side_effect=AssertionError("offline")), patch(
                "socket.create_connection", side_effect=AssertionError("offline")
            ):
                provider = PiperTTSProvider(data_directory=root)
                samples = (
                    ("en", "Hello, this is TARS. It's 8 o'clock, and I can speak English."),
                    ("fr", "Bonjour, je suis TARS. À bientôt, l'été arrive et il est 8 heures."),
                )
                for index, (language, text) in enumerate(samples * 2):
                    with self.subTest(language=language, switch=index):
                        provider.set_language(language)
                        self.assertTrue(provider.installed)
                        provider.initialize()
                        model = provider._model
                        self.assertTrue(model.config.espeak_voice.lower().startswith(language))
                        self.assertEqual(model.session.get_providers(), ["CPUExecutionProvider"])
                        provider.initialize()
                        self.assertIs(provider._model, model)
                        chunks = list(provider.generate_stream(text, threading.Event()))
                        self.assertGreaterEqual(len(chunks), 2)
                        self.assertEqual({rate for _, rate in chunks}, {22050})
                        audio = np.frombuffer(b"".join(pcm for pcm, _ in chunks), dtype=np.float32)
                        self.assertGreater(audio.size, 22050)
                        self.assertTrue(np.isfinite(audio).all())
                        self.assertGreater(float(np.max(np.abs(audio))), 0.01)
                        output = provider.generate(text, root / f"{language}.wav")
                        with wave.open(str(output), "rb") as wav_file:
                            self.assertEqual(wav_file.getnchannels(), 1)
                            self.assertEqual(wav_file.getsampwidth(), 2)
                            self.assertEqual(wav_file.getframerate(), 22050)
                            self.assertGreater(wav_file.getnframes(), 22050)
                        audio_format = QAudioFormat()
                        audio_format.setSampleRate(48000)
                        audio_format.setChannelCount(2)
                        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
                        converted = AudioPlayback._convert(chunks[0][0], 22050, audio_format)
                        self.assertGreater(len(converted), 0)
                        self.assertEqual(len(converted) % audio_format.bytesPerFrame(), 0)
                        stop = threading.Event()
                        stream = provider.generate_stream(text, stop)
                        self.assertTrue(next(stream)[0])
                        stop.set()
                        self.assertEqual(list(stream), [])
                        self.check_service_playback(provider, text)
                        print(f"Piper {language}: offline WAV/stream, language switch and Qt service playback passed", flush=True)
                provider.shutdown()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
