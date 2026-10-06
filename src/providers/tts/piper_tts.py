from __future__ import annotations

import hashlib
import json
import logging
import threading
import wave
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from core.paths import data_directory as user_data_directory, resource_directory


logger = logging.getLogger("TARS.PiperTTS")


class _FrenchAudioProcessor:
    """Subtle EQ and compression, retaining state between streamed chunks."""

    def __init__(self, sample_rate: int) -> None:
        import numpy as np

        self.sample_rate = sample_rate
        # Broad peaking filters: a little warmth and less upper-mid harshness.
        sections = []
        for frequency, gain_db in ((180.0, 1.0), (3500.0, -1.5)):
            omega = 2 * np.pi * min(frequency, sample_rate * 0.45) / sample_rate
            amplitude = 10 ** (gain_db / 40)
            alpha = np.sin(omega) / 2  # Q = 1.
            cosine = np.cos(omega)
            section = np.array([
                1 + alpha * amplitude, -2 * cosine, 1 - alpha * amplitude,
                1 + alpha / amplitude, -2 * cosine, 1 - alpha / amplitude,
            ])
            sections.append(section / section[3])
        self._eq = np.array(sections)
        self._eq_state = np.zeros((len(sections), 2))
        self._envelope = 0.0
        self._attack = np.exp(-1 / (sample_rate * 0.010))
        self._release = np.exp(-1 / (sample_rate * 0.120))

    def process(self, audio: Any) -> Any:
        import numpy as np
        from scipy.signal import sosfilt

        if not audio.size:
            return audio.astype(np.float32, copy=False)
        filtered, self._eq_state = sosfilt(self._eq, audio, zi=self._eq_state)
        envelope = np.empty(filtered.size)
        level = self._envelope
        for index, peak in enumerate(np.abs(filtered)):
            coefficient = self._attack if peak > level else self._release
            level = coefficient * level + (1 - coefficient) * peak
            envelope[index] = level
        self._envelope = level

        # A 1.5:1 compressor at -18 dBFS with a 6 dB soft knee. No makeup
        # gain or normalization: quiet passages and silence stay quiet.
        above_threshold = 20 * np.log10(np.maximum(envelope, 1e-12)) + 18
        knee = 6.0
        slope = 1 / 1.5 - 1
        gain_db = np.where(
            above_threshold <= -knee / 2, 0.0,
            np.where(above_threshold >= knee / 2, slope * above_threshold,
                     slope * (above_threshold + knee / 2) ** 2 / (2 * knee)),
        )
        return np.clip(filtered * 10 ** (gain_db / 20), -1.0, 1.0).astype(np.float32)


class PiperTTSProvider:
    """Local CPU synthesis with separate downloadable French and English voices."""

    # Keep the voice's trained timbre and conversational speed, with more
    # duration variation. Fixed gain preserves dynamics between sentences;
    # Piper's per-sentence peak normalization otherwise makes each equally loud.
    SYNTHESIS_SETTINGS = {
        "length_scale": 1.0,
        "noise_scale": 0.667,
        "noise_w_scale": 1.0,
        "normalize_audio": False,
        "volume": 1.25,
    }
    # Near-natural phoneme durations without changing the trained pitch.
    FRENCH_SYNTHESIS_SETTINGS = {**SYNTHESIS_SETTINGS, "length_scale": 1.02}
    BUNDLED_FRENCH_DIRECTORY = Path("src/providers/tts/fr-siwis-medium")
    PUNCTUATION_PAUSES = {".": 0.24, "?": 0.30, "!": 0.20,
                          ";": 0.14, ":": 0.14, ",": 0.08}

    PUBLIC_REPOSITORY = "rhasspy/piper-voices"
    VOICES_REVISION = "c10ece1aade47bb51c153c893d14e5bf8e5b7117"
    MODEL_SIZE = 63201294
    LANGUAGES = {
        "en": {
            "voice": "en_US-lessac-medium",
            "directory": "en/en_US/lessac/medium",
            "model_md5": "2fc642b535197b6305c7c8f92dc8b24f",
            "config_size": 4885,
            "config_md5": "c1f2b7bddefe113f3255ff9ef234cfd3",
        },
        "fr": {
            "voice": "fr_FR-siwis-medium",
            "directory": "fr/fr_FR/siwis/medium",
            "model_md5": "20e876e8c839e9b11a26085858f2300c",
            "config_size": 4875,
            "config_md5": "a407e7e6901feb79c2ea2a5466076cce",
        },
    }

    def __init__(self, language: str = "en", *, data_directory: Path | None = None) -> None:
        self._language_info(language)
        self._data_directory = data_directory or user_data_directory() / "tts"
        self._resources_directory = self._data_directory / "piper"
        self._installation_marker = self._data_directory / "piper_tts_installed.json"
        self._language = language
        self._model: Any | None = None
        self._loaded_language: str | None = None

    @property
    def language(self) -> str:
        return self._language

    @property
    def installed(self) -> bool:
        return self.resources_available(self._language) and (
            self._bundled_voice_available(self._language) or self._installation_marker.is_file()
        )

    @property
    def initialized(self) -> bool:
        return self._model is not None

    def set_language(self, language: str) -> None:
        self._language_info(language)
        if language != self._language:
            self.shutdown()
            self._language = language

    def initialize(self, on_status: Callable[[str], None] | None = None) -> None:
        """Load installed files without any network access."""
        if not self.installed:
            raise RuntimeError(
                "Piper TTS n'est pas installé pour cette langue. "
                "Cliquez sur le bouton de téléchargement."
            )
        self.load(self._language, on_status=on_status)

    def download(self, on_status: Callable[[str], None] | None = None) -> None:
        """Install only the selected voice after an explicit download action."""
        try:
            self.shutdown()
            self._download_resources(self._language, on_status=on_status)
            self.load(self._language, on_status=on_status)
            marker = {
                "provider": "piper-tts", "language": self._language,
                "voice": self._language_info(self._language)["voice"], "offline": True,
            }
            self._data_directory.mkdir(parents=True, exist_ok=True)
            temporary = self._installation_marker.with_suffix(".tmp")
            temporary.write_text(json.dumps(marker, indent=2), encoding="utf-8")
            temporary.replace(self._installation_marker)
            if on_status:
                on_status("Moteur vocal installé et disponible hors ligne.")
        except Exception:
            logger.exception("[T.A.R.S.][TTS] Échec de l'installation de Piper.")
            self.shutdown()
            raise

    def resources_available(self, language: str) -> bool:
        """Reject missing, empty or truncated files without hashing on every UI query."""
        info = self._language_info(language)
        return all(
            path.is_file() and path.stat().st_size == size
            for path, size in (
                (self._model_path(language), self.MODEL_SIZE),
                (self._config_path(language), info["config_size"]),
            )
        )

    def _download_resources(self, language: str,
                            on_status: Callable[[str], None] | None = None) -> None:
        if self._bundled_voice_available(language):
            if on_status:
                on_status("Voix française Piper disponible localement.")
            return
        from huggingface_hub import hf_hub_download

        info = self._language_info(language)
        self._resources_directory.mkdir(parents=True, exist_ok=True)
        for path, message, digest in (
            (self._model_path(language), "Téléchargement du modèle Piper TTS...", info["model_md5"]),
            (self._config_path(language), "Téléchargement de la configuration Piper TTS...", info["config_md5"]),
        ):
            if on_status:
                on_status(message)
            filename = path.relative_to(self._resources_directory).as_posix()
            hf_hub_download(
                repo_id=self.PUBLIC_REPOSITORY, filename=filename,
                revision=self.VOICES_REVISION, local_dir=str(self._resources_directory),
                force_download=path.exists() and not self._matches_digest(path, digest),
            )
            if not self._matches_digest(path, digest):
                raise RuntimeError("Les fichiers téléchargés de Piper TTS sont incomplets ou corrompus.")

    @staticmethod
    def _matches_digest(path: Path, expected: str) -> bool:
        with path.open("rb") as resource:
            return hashlib.file_digest(resource, "md5").hexdigest() == expected

    def load(self, language: str, on_status: Callable[[str], None] | None = None) -> None:
        if self.initialized and self._loaded_language == language:
            return
        self.shutdown()
        if not self.resources_available(language):
            raise RuntimeError("Les fichiers locaux de Piper TTS pour cette langue sont incomplets.")
        if on_status:
            on_status("Chargement du modèle Piper TTS local...")
        from piper import PiperVoice

        self._model = PiperVoice.load(
            str(self._model_path(language)), config_path=str(self._config_path(language)),
            use_cuda=False,
        )
        self._loaded_language = language
        if on_status:
            on_status("Moteur vocal prêt.")

    def generate(self, text: str, output_path: Path) -> Path:
        """Write the same phrasing and dynamics as streaming to a PCM WAV."""
        if self._model is None:
            raise RuntimeError("Piper TTS n'est pas initialisé.")
        import numpy as np

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._model.config.sample_rate)
            for pcm, _ in self.generate_stream(text, threading.Event()):
                audio = np.frombuffer(pcm, dtype=np.float32)
                wav_file.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes())
        return output_path

    def generate_stream(self, text: str, stop: threading.Event) -> Iterator[tuple[bytes, int]]:
        """Adapt Piper's sentence chunks to Qt's mono float32 PCM contract."""
        if self._model is None:
            raise RuntimeError("Piper TTS n'est pas initialisé.")
        if stop.is_set() or not text.strip():
            return
        from piper import SynthesisConfig

        french = (self._loaded_language or self._language) == "fr"
        settings = self.FRENCH_SYNTHESIS_SETTINGS if french else self.SYNTHESIS_SETTINGS
        syn_config = SynthesisConfig(**settings)
        processor = None
        for chunk in self._model.synthesize(text.strip(), syn_config=syn_config):
            if stop.is_set():
                break
            if chunk.sample_channels != 1:
                raise RuntimeError("Piper TTS doit produire un flux audio mono.")
            audio = self._add_pause(chunk.audio_float_array, chunk.sample_rate, chunk.phonemes)
            if french:
                if processor is None or processor.sample_rate != chunk.sample_rate:
                    processor = _FrenchAudioProcessor(chunk.sample_rate)
                audio = processor.process(audio)
            yield audio.astype("float32", copy=False).tobytes(), chunk.sample_rate
            if stop.is_set():
                break

    @classmethod
    def _add_pause(cls, audio: Any, sample_rate: int, phonemes: list[str]) -> Any:
        """Complete a punctuation pause without duplicating the model's silence."""
        import numpy as np

        ending = "".join(phonemes).rstrip(' \t\n\"\'»”)]')[-1:]
        pause_samples = round(cls.PUNCTUATION_PAUSES.get(ending, 0.0) * sample_rate)
        if not pause_samples or not audio.size:
            return audio
        # Inspect only the tail. Leave quiet speech and all existing samples
        # intact; add just the missing silence, including across queued texts.
        tail = audio[-pause_samples:]
        audible = np.flatnonzero(np.abs(tail) > 0.003)
        silence_samples = tail.size - audible[-1] - 1 if audible.size else tail.size
        missing = pause_samples - silence_samples
        if missing > 0:
            return np.concatenate((audio, np.zeros(missing, dtype=audio.dtype)))
        return audio

    def shutdown(self) -> None:
        self._model = None
        self._loaded_language = None

    @classmethod
    def _language_info(cls, language: str) -> dict[str, Any]:
        try:
            return cls.LANGUAGES[language]
        except KeyError as exc:
            raise ValueError(f"Langue Piper TTS non prise en charge : {language}") from exc

    def _model_path(self, language: str) -> Path:
        info = self._language_info(language)
        if self._bundled_voice_available(language):
            return resource_directory() / self.BUNDLED_FRENCH_DIRECTORY / "model.onnx"
        return self._resources_directory / info["directory"] / f"{info['voice']}.onnx"

    def _config_path(self, language: str) -> Path:
        return self._model_path(language).with_suffix(".onnx.json")

    def _bundled_voice_available(self, language: str) -> bool:
        if language != "fr":
            return False
        directory = resource_directory() / self.BUNDLED_FRENCH_DIRECTORY
        return all(
            path.is_file() and path.stat().st_size == size
            for path, size in (
                (directory / "model.onnx", self.MODEL_SIZE),
                (directory / "model.onnx.json", self.LANGUAGES["fr"]["config_size"]),
            )
        )
