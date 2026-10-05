from __future__ import annotations

import hashlib
import json
import logging
import threading
import wave
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from core.paths import data_directory as user_data_directory


logger = logging.getLogger("TARS.PiperTTS")


class PiperTTSProvider:
    """Local CPU synthesis with separate downloadable French and English voices."""

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
        return self._installation_marker.is_file() and self.resources_available(self._language)

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
        """Write a standard PCM WAV file using the loaded local voice."""
        if self._model is None:
            raise RuntimeError("Piper TTS n'est pas initialisé.")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "wb") as wav_file:
            self._model.synthesize_wav(text.strip(), wav_file)
        return output_path

    def generate_stream(self, text: str, stop: threading.Event) -> Iterator[tuple[bytes, int]]:
        """Adapt Piper's sentence chunks to Qt's mono float32 PCM contract."""
        if self._model is None:
            raise RuntimeError("Piper TTS n'est pas initialisé.")
        if stop.is_set() or not text.strip():
            return
        for chunk in self._model.synthesize(text.strip()):
            if stop.is_set():
                break
            if chunk.sample_channels != 1:
                raise RuntimeError("Piper TTS doit produire un flux audio mono.")
            yield chunk.audio_float_array.astype("float32", copy=False).tobytes(), chunk.sample_rate
            if stop.is_set():
                break

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
        return self._resources_directory / info["directory"] / f"{info['voice']}.onnx"

    def _config_path(self, language: str) -> Path:
        return self._model_path(language).with_suffix(".onnx.json")
