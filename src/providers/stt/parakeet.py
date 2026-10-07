from __future__ import annotations

import json
import logging
import tempfile
import traceback
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from core.paths import data_directory as user_data_directory
from core.runtime_resources import cpu_threads, release_unused_memory


if TYPE_CHECKING:
    import torch


logger = logging.getLogger("TARS.Parakeet")


class ParakeetProvider:
    """Technical access to the local Parakeet checkpoint only."""

    REPOSITORY = "nvidia/parakeet-tdt-0.6b-v3"
    MODEL_FILE = "parakeet-tdt-0.6b-v3.nemo"
    CPU_THREADS = cpu_threads()

    def __init__(self, data_directory: Path | None = None) -> None:
        data_directory = data_directory or user_data_directory() / "stt"
        self._data_directory = data_directory
        self._installation_marker = data_directory / "parakeet_installed.json"
        self._model_path = data_directory / self.MODEL_FILE
        self._model: Any | None = None
        self._checkpoint_directory: tempfile.TemporaryDirectory | None = None

    @property
    def installed(self) -> bool:
        """Return whether required local resources are installed."""
        return (
            self._installation_marker.exists()
            and self.model_available
        )

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Load the installed provider."""
        if not self.installed:
            raise RuntimeError(
                "Parakeet n'est pas installé. Cliquez sur le bouton "
                "de téléchargement."
            )
        self.load(on_status=on_status)

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Download and prepare the provider resources."""
        self.shutdown()
        self._download_resources(on_status=on_status)
        self.load(on_status=on_status)
        self._write_installation_marker()

    def _write_installation_marker(self) -> None:
        temporary_file = self._installation_marker.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(
                {
                    "provider": "parakeet-tdt-0.6b-v3",
                    "offline": True,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary_file.replace(self._installation_marker)

    @property
    def model_available(self) -> bool:
        """Return whether the local model files are present."""
        return self._model_path.is_file()

    def _download_resources(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Download and prepare the provider resources."""
        from huggingface_hub import hf_hub_download

        if on_status:
            on_status("Téléchargement de Parakeet (environ 2,5 Go)...")

        self._data_directory.mkdir(parents=True, exist_ok=True)
        hf_hub_download(
            repo_id=self.REPOSITORY,
            filename=self.MODEL_FILE,
            local_dir=str(self._data_directory),
        )

    def load(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Load the installed provider resources."""
        if self._model is not None:
            return
        if not self.model_available:
            raise RuntimeError("Le checkpoint local de Parakeet est introuvable.")
        if on_status:
            on_status("Chargement local de Parakeet...")

        import torch

        torch.set_num_threads(self.CPU_THREADS)
        nemo_asr = self._import_nemo()
        from nemo.utils import logging as nemo_logging
        from providers.stt.checkpoint import InferenceSaveRestoreConnector

        nemo_logging.setLevel(logging.ERROR)
        # Keep the extracted checkpoint alive while tensors map its storage.
        # In particular, Windows cannot delete files with live mappings.
        # Use the checkpoint's filesystem: /tmp may be a RAM-backed tmpfs.
        connector = InferenceSaveRestoreConnector()
        try:
            if self._checkpoint_directory is None:
                self._checkpoint_directory = tempfile.TemporaryDirectory(
                    prefix=".parakeet-", dir=self._data_directory,
                )
                connector._unpack_nemo_file(
                    path2file=str(self._model_path),
                    out_folder=self._checkpoint_directory.name,
                )
            connector.model_extracted_dir = self._checkpoint_directory.name
            self._model = nemo_asr.models.ASRModel.restore_from(
                restore_path=str(self._model_path),
                map_location="cpu",
                save_restore_connector=connector,
            )
            self._model.freeze()
        except Exception as exc:
            # Failed restore frames can retain mapped tensors. Clear their
            # locals before removing the backing file, also on Windows.
            traceback.clear_frames(exc.__traceback__)
            self.shutdown()
            raise
        release_unused_memory(collect=True)

    def transcribe(self, audio_path: Path, language: str = "en") -> str:
        """Convert an audio file into text."""
        try:
            return self._transcribe(audio_path, language)
        finally:
            # Inference activations are no longer live after the helper returns.
            release_unused_memory()

    def _transcribe(self, audio_path: Path, language: str) -> str:
        if self._model is None:
            raise RuntimeError("Parakeet n'est pas initialisé.")

        import torch

        torch.set_num_threads(self.CPU_THREADS)
        audio = self._read_audio(audio_path)
        with torch.inference_mode():
            result = self._model.transcribe(
                [audio],
                use_lhotse=False,
                batch_size=1,
                num_workers=0,
                verbose=False,
            )[0]
        text = getattr(result, "text", result)
        text = str(text).strip()
        if language == "en":
            text = self._normalise_english_script(text)
        return text

    @staticmethod
    def _normalise_english_script(text: str) -> str:
        """Convert accidental Cyrillic phonetic output for English Pocket TTS."""
        if not any("\u0400" <= character <= "\u04ff" for character in text):
            return text

        transliteration = str.maketrans(
            {
                "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D",
                "Е": "E", "Ё": "Yo", "Ж": "Zh", "З": "Z", "И": "I",
                "Й": "Y", "К": "K", "Л": "L", "М": "M", "Н": "N",
                "О": "O", "П": "P", "Р": "R", "С": "S", "Т": "T",
                "У": "U", "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch",
                "Ш": "Sh", "Щ": "Shch", "Ъ": "", "Ы": "Y", "Ь": "",
                "Э": "E", "Ю": "Yu", "Я": "Ya",
                "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
                "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
                "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
                "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
                "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
                "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
                "э": "e", "ю": "yu", "я": "ya",
            }
        )
        normalised = text.translate(transliteration)

        words = {"ze": "the", "Ze": "The"}
        return " ".join(words.get(word, word) for word in normalised.split())

    @staticmethod
    def _read_audio(audio_path: Path) -> torch.Tensor:
        """Load the recorder PCM data without creating a NeMo manifest."""
        import torch

        with wave.open(str(audio_path), "rb") as source:
            if (
                source.getframerate() != 16_000
                or source.getnchannels() != 1
                or source.getsampwidth() != 2
            ):
                raise RuntimeError(
                    "Parakeet attend un fichier WAV mono 16 kHz sur 16 bits."
                )
            payload = bytearray(source.readframes(source.getnframes()))
        return (
            torch.frombuffer(payload, dtype=torch.int16)
            .to(torch.float32)
            .div_(32768.0)
        )

    def release_model(self) -> None:
        """Unmap idle weights, retaining the extracted checkpoint for reuse."""
        had_model = self._model is not None
        self._model = None
        if had_model:
            release_unused_memory(collect=True)

    def shutdown(self) -> None:
        """Release provider resources and remove the extracted checkpoint."""
        self.release_model()
        if self._checkpoint_directory is not None:
            self._checkpoint_directory.cleanup()
            self._checkpoint_directory = None

    @staticmethod
    def _import_nemo() -> Any:
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise RuntimeError(
                "La dépendance Parakeet est absente. Exécutez "
                "'uv sync' puis relancez T.A.R.S."
            ) from exc
        return nemo_asr
