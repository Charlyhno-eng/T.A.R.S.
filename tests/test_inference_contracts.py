from __future__ import annotations

import sys
import tempfile
import threading
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import torch
import yaml
from scipy.io import wavfile

from providers.stt.parakeet import ParakeetProvider
from providers.tts.pocket_tts import PocketTTSProvider


class ParakeetInferenceTests(unittest.TestCase):
    def test_recorder_format_validation_and_pcm_normalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.wav"
            for rate, channels, width in ((8000, 1, 2), (16000, 2, 2), (16000, 1, 1), (16000, 1, 2)):
                with self.subTest(rate=rate, channels=channels, width=width):
                    with wave.open(str(path), "wb") as output:
                        output.setparams((channels, width, rate, 0, "NONE", ""))
                        output.writeframes(np.array([-32768, 0, 32767], dtype=np.int16).tobytes())
                    if (rate, channels, width) != (16000, 1, 2):
                        with self.assertRaisesRegex(RuntimeError, "WAV mono"):
                            ParakeetProvider._read_audio(path)
                    else:
                        audio = ParakeetProvider._read_audio(path)
                        torch.testing.assert_close(audio, torch.tensor([-1., 0., 32767 / 32768]))

    def test_transcription_accepts_hypotheses_and_strings_and_keeps_french_script(self):
        provider = ParakeetProvider()
        provider._model = Mock()
        audio = torch.zeros(1600)
        for result, language, expected in ((SimpleNamespace(text="  Зе ТАРС  "), "en", "The TARS"),
                                           (" Bonjour. ", "fr", "Bonjour."),
                                           ("  Зе ТАРС  ", "fr", "Зе ТАРС"),
                                           ("Hello.", "en", "Hello.")):
            with self.subTest(language=language, result=result), patch.object(
                provider, "_read_audio", return_value=audio
            ), patch("providers.stt.parakeet.release_unused_memory") as trim:
                provider._model.transcribe.return_value = [result]
                self.assertEqual(provider.transcribe(Path("input.wav"), language), expected)
                provider._model.transcribe.assert_called_with(
                    [audio], use_lhotse=False, batch_size=1, num_workers=0, verbose=False)
                trim.assert_called_once()
        provider._model = None
        with patch("providers.stt.parakeet.release_unused_memory") as trim:
            with self.assertRaisesRegex(RuntimeError, "initialisé"):
                provider.transcribe(Path("input.wav"))
            trim.assert_called_once()

    def test_download_uses_configured_model_and_loading_requires_a_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = ParakeetProvider(data_directory=Path(directory))
            with self.assertRaisesRegex(RuntimeError, "introuvable"):
                provider.load()
            status = Mock()
            with patch("huggingface_hub.hf_hub_download") as download:
                provider._download_resources(on_status=status)
            self.assertEqual(download.call_args.kwargs["filename"], provider.MODEL_FILE)
            self.assertEqual(download.call_args.kwargs["local_dir"], directory)
            self.assertEqual(download.call_args.kwargs["repo_id"], provider.REPOSITORY)
            status.assert_called_once()


class PocketInferenceTests(unittest.TestCase):
    def test_download_local_config_load_generate_and_cancel_for_both_languages(self):
        for language in ("en", "fr"):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                provider = PocketTTSProvider(language, data_directory=root / "data")
                package = root / "package"
                (package / "config").mkdir(parents=True)
                pocket_language = provider.LANGUAGES[language]["pocket_language"]
                (package / "config" / f"{pocket_language}.yaml").write_text(
                    "weights_path: remote\nflow_lm:\n  lookup_table:\n    tokenizer_path: remote\n")
                model = Mock(sample_rate=24000)
                model.get_state_for_audio_prompt.return_value = {"voice": language}
                model.generate_audio.return_value = torch.tensor([0.25, -0.5])
                loader = Mock(return_value=model)
                module = SimpleNamespace(__file__=str(package / "__init__.py"),
                                         TTSModel=SimpleNamespace(load_model=loader))

                def download(**kwargs):
                    target = Path(kwargs["local_dir"]) / kwargs["filename"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.touch()
                    return str(target)

                status = Mock()
                with patch.dict(sys.modules, {"pocket_tts": module}), patch(
                    "huggingface_hub.hf_hub_download", side_effect=download
                ) as downloads:
                    provider.download(on_status=status)
                    self.assertTrue(provider.installed)
                    self.assertTrue(provider.initialized)
                    self.assertEqual(downloads.call_count, 3)
                    self.assertEqual(downloads.call_args_list[-1].kwargs["revision"], provider.VOICE_REVISION)
                    config = yaml.safe_load(provider._config_path(language).read_text())
                    self.assertEqual(config["weights_path"], str(provider._model_path(language)))
                    self.assertEqual(config["flow_lm"]["lookup_table"]["tokenizer_path"],
                                     str(provider._tokenizer_path(language)))
                    provider.initialize(on_status=status)
                    provider.set_language(language)
                    loader.assert_called_once_with(config=provider._config_path(language))
                    output = root / "audio" / "output.wav"
                    self.assertEqual(provider.generate("  Hello  ", output), output)
                    rate, samples = wavfile.read(output)
                    self.assertEqual(rate, 24000)
                    np.testing.assert_array_equal(samples, [0.25, -0.5])
                    model.generate_audio.assert_called_once_with({"voice": language}, "Hello")
                    stop = threading.Event()

                    def chunks(*args, **kwargs):
                        yield torch.tensor([0.25])
                        stop.set()
                        yield torch.tensor([0.5])

                    model.generate_audio_stream.side_effect = chunks
                    pcm = list(provider.generate_stream(" Hello ", stop))
                    self.assertEqual(len(pcm), 1)
                    self.assertEqual(pcm[0], (np.array([0.25], dtype=np.float32).tobytes(), 24000))
                    provider.shutdown()
                    provider.load(language, on_status=status)
                    self.assertEqual(loader.call_count, 2)
                    provider.shutdown()

    def test_incomplete_resources_and_uninitialized_generation_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            provider = PocketTTSProvider(data_directory=Path(directory))
            with self.assertRaisesRegex(RuntimeError, "incomplets"):
                provider.load("en")
            for action in (lambda: provider.generate("Hello", Path(directory) / "out.wav"),
                           lambda: list(provider.generate_stream("Hello", threading.Event()))):
                with self.assertRaisesRegex(RuntimeError, "initialisé"):
                    action()
            with self.assertRaises(ValueError):
                provider.resources_available("de")
