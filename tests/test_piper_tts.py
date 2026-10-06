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
from providers.tts.piper_tts import PiperTTSProvider, _FrenchAudioProcessor


class PiperTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.provider = PiperTTSProvider(data_directory=Path(directory.name))
        self.resources = Path(directory.name) / "bundle"
        patcher = patch("providers.tts.piper_tts.resource_directory", return_value=self.resources)
        patcher.start()
        self.addCleanup(patcher.stop)
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

    def test_bundled_voice_is_preferred_and_ready_only_for_french_piper(self) -> None:
        from providers.tts.pocket_tts import PocketTTSProvider

        directory = self.resources / self.provider.BUNDLED_FRENCH_DIRECTORY
        directory.mkdir(parents=True)
        (directory / "model.onnx").write_bytes(b"onnx")
        (directory / "model.onnx.json").write_bytes(b"{}")
        # Previously downloaded voices must not shadow the supplied model.
        cached_model = (self.provider._resources_directory / self.languages["fr"]["directory"]
                        / f"{self.languages['fr']['voice']}.onnx")
        cached_model.parent.mkdir(parents=True)
        cached_model.write_bytes(b"onnx")
        cached_model.with_suffix(".onnx.json").write_bytes(b"{}")
        self.assertFalse(self.provider.installed)  # English still needs installation.
        self.assertFalse(PocketTTSProvider("fr", data_directory=self.provider._data_directory).installed)
        self.provider.set_language("fr")
        self.assertTrue(self.provider.installed)
        self.assertFalse(self.provider._installation_marker.exists())
        with patch("huggingface_hub.hf_hub_download", side_effect=AssertionError("network")), patch(
            "piper.PiperVoice.load", return_value=Mock()
        ) as load:
            self.provider.initialize()
            load.assert_called_once_with(str(directory / "model.onnx"),
                                         config_path=str(directory / "model.onnx.json"), use_cuda=False)
            self.provider.download()
            fresh = PiperTTSProvider("fr", data_directory=self.provider._data_directory / "fresh")
            fresh.download()
            self.assertTrue(fresh._installation_marker.is_file())
        self.provider.set_language("en")
        self.assertFalse(self.provider.installed)
        self.assertEqual(self.provider._model_path("en").name, "en_US-lessac-medium.onnx")

    def test_incomplete_bundled_voice_falls_back_to_downloaded_resources(self) -> None:
        directory = self.resources / self.provider.BUNDLED_FRENCH_DIRECTORY
        directory.mkdir(parents=True)
        (directory / "model.onnx").write_bytes(b"bad")
        (directory / "model.onnx.json").write_bytes(b"{}")
        self.provider.set_language("fr")
        self.assertFalse(self.provider.installed)
        with patch("huggingface_hub.hf_hub_download", side_effect=self.download_file) as download, patch(
            "piper.PiperVoice.load", return_value=Mock()
        ):
            self.provider.download()
        self.assertEqual(download.call_count, 2)
        self.assertTrue(self.provider.installed)
        self.assertEqual(self.provider._model_path("fr").name, "fr_FR-siwis-medium.onnx")
        self.assertEqual((directory / "model.onnx").read_bytes(), b"bad")

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
        chunk = SimpleNamespace(sample_channels=1, sample_rate=22050,
                                audio_float_array=audio, phonemes=[])
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

    def test_punctuation_pauses_preserve_speech_and_existing_silence(self) -> None:
        rate = 1000
        speech = np.array([0.1, -0.2, 0.3], dtype=np.float32)
        for ending, duration in ((".", 0.24), ("?", 0.30), ("!", 0.20), (",", 0.08)):
            with self.subTest(ending=ending):
                audio = np.concatenate((speech, np.zeros(20, dtype=np.float32)))
                result = self.provider._add_pause(audio, rate, ["a", ending, "”"])
                np.testing.assert_array_equal(result[:audio.size], audio)
                self.assertEqual(result.size, speech.size + round(duration * rate))
                self.assertFalse(np.any(result[speech.size:]))
        for audio, phonemes in (
            (np.concatenate((speech, np.zeros(500, dtype=np.float32))), ["a", "."]),
            (speech, ["a"]),  # No artificial pause in an unfinished fragment.
            (np.array([], dtype=np.float32), ["."]),
        ):
            self.assertIs(self.provider._add_pause(audio, rate, phonemes), audio)

    def test_wav_and_stream_share_dynamics_and_punctuation_pauses(self) -> None:
        from piper import SynthesisConfig

        self.provider._model = Mock()
        self.provider._model.config.sample_rate = 22050
        audio = np.array([0.1, -0.2, 0.3], dtype=np.float32)
        chunk = SimpleNamespace(sample_channels=1, sample_rate=22050,
                                audio_float_array=audio, phonemes=["a", "."])
        self.provider._model.synthesize.side_effect = lambda *args, **kwargs: iter([chunk])
        streamed = b"".join(pcm for pcm, _ in self.provider.generate_stream("Hello.", threading.Event()))
        output = self.provider.generate("Hello.", self.provider._data_directory / "sample.wav")
        with wave.open(str(output), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getframerate(), 22050)
            pcm = wav_file.readframes(wav_file.getnframes())
        expected = (np.frombuffer(streamed, dtype=np.float32) * 32767).astype(np.int16)
        np.testing.assert_array_equal(np.frombuffer(pcm, dtype=np.int16), expected)
        for call in self.provider._model.synthesize.call_args_list:
            config = call.kwargs["syn_config"]
            self.assertIsInstance(config, SynthesisConfig)
            self.assertFalse(config.normalize_audio)
            self.assertEqual(config.volume, 1.25)

    def test_french_siwis_uses_own_pacing_and_processing_in_stream_and_wav(self) -> None:
        self.provider.set_language("fr")
        self.assertEqual(self.provider._model_path("fr").name, "fr_FR-siwis-medium.onnx")
        rate = 22050
        audio = (0.6 * np.sin(2 * np.pi * 1000 * np.arange(rate) / rate)).astype(np.float32)
        chunk = SimpleNamespace(sample_channels=1, sample_rate=rate,
                                audio_float_array=audio, phonemes=["a", "."])
        self.provider._model = Mock()
        self.provider._model.config.sample_rate = rate
        self.provider._model.synthesize.side_effect = lambda *args, **kwargs: iter([chunk, chunk])
        streamed = np.frombuffer(b"".join(
            pcm for pcm, _ in self.provider.generate_stream("Bonjour. À bientôt.", threading.Event())
        ), dtype=np.float32)
        self.assertFalse(np.array_equal(streamed[:audio.size], audio))
        # The attack deliberately preserves the onset; sustained peaks soften.
        self.assertLess(np.max(np.abs(streamed[rate // 2:rate])), np.max(np.abs(audio)))
        self.assertGreater(streamed.size, 2 * audio.size)  # Punctuation pauses remain.
        output = self.provider.generate("Bonjour. À bientôt.", self.provider._data_directory / "fr.wav")
        with wave.open(str(output), "rb") as wav_file:
            pcm = wav_file.readframes(wav_file.getnframes())
        np.testing.assert_array_equal(
            np.frombuffer(pcm, dtype=np.int16), (streamed * 32767).astype(np.int16)
        )
        for call in self.provider._model.synthesize.call_args_list:
            config = call.kwargs["syn_config"]
            self.assertEqual(config.length_scale, 1.02)
            self.assertFalse(config.normalize_audio)
        self.provider.set_language("en")
        self.provider._model = Mock()
        self.provider._model.synthesize.return_value = iter([chunk])
        pcm, _ = next(self.provider.generate_stream("Hello.", threading.Event()))
        np.testing.assert_array_equal(np.frombuffer(pcm, dtype=np.float32)[:audio.size], audio)
        self.assertEqual(self.provider._model.synthesize.call_args.kwargs["syn_config"].length_scale, 1.0)


class FrenchAudioTests(unittest.TestCase):
    def test_processing_is_independent_of_chunk_boundaries_and_resets_per_utterance(self) -> None:
        rate = 22050
        audio = (0.5 * np.sin(2 * np.pi * 180 * np.arange(rate) / rate)).astype(np.float32)
        whole = _FrenchAudioProcessor(rate).process(audio)
        processor = _FrenchAudioProcessor(rate)
        chunks = [processor.process(chunk) for chunk in np.array_split(audio, 17)]
        np.testing.assert_array_equal(np.concatenate(chunks), whole)
        np.testing.assert_array_equal(_FrenchAudioProcessor(rate).process(audio), whole)
        self.assertEqual(whole.dtype, np.float32)
        self.assertEqual(whole.size, audio.size)
        self.assertEqual(processor.process(np.array([], dtype=np.float32)).size, 0)

    def test_eq_is_subtle_and_compression_preserves_quiet_audio_and_silence(self) -> None:
        rate = 22050
        for frequency, expected_db in ((180, 1.0), (3500, -1.5)):
            with self.subTest(frequency=frequency):
                quiet = 0.01 * np.sin(2 * np.pi * frequency * np.arange(rate) / rate)
                processed = _FrenchAudioProcessor(rate).process(quiet)
                gain_db = 20 * np.log10(np.linalg.norm(processed[rate // 2:])
                                        / np.linalg.norm(quiet[rate // 2:]))
                self.assertAlmostEqual(gain_db, expected_db, delta=0.1)
        for amplitude in (0.03, 0.6):
            processor = _FrenchAudioProcessor(rate)
            audio = np.full(rate, amplitude, dtype=np.float32)
            processed = processor.process(audio)
            if amplitude == 0.03:
                self.assertAlmostEqual(float(processed[-1]), amplitude, places=6)
            else:
                self.assertLess(float(processed[-1]), amplitude * 0.8)
                self.assertGreater(float(processed[-1]), amplitude * 0.5)
            silence = processor.process(np.zeros(rate, dtype=np.float32))
            np.testing.assert_allclose(silence[rate // 2:], 0, atol=1e-12)
        loud = _FrenchAudioProcessor(rate).process(np.array([4.0, -4.0, 0.0]))
        self.assertTrue(np.isfinite(loud).all())
        self.assertLessEqual(float(np.max(np.abs(loud))), 1.0)


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
