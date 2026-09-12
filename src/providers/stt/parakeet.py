from __future__ import annotations

import logging
import os
import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable


if TYPE_CHECKING:
    import torch


logger = logging.getLogger("TARS.Parakeet")


class ParakeetProvider:
    """Technical access to the local Parakeet checkpoint only."""

    REPOSITORY = "nvidia/parakeet-tdt-0.6b-v3"
    MODEL_FILE = "parakeet-tdt-0.6b-v3.nemo"
    CPU_THREADS = min(4, len(os.sched_getaffinity(0)))

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._model_path = data_directory / self.MODEL_FILE
        self._model: Any | None = None

    @property
    def model_available(self) -> bool:
        return self._model_path.is_file()

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
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
        if self._model is not None:
            return
        if not self.model_available:
            raise RuntimeError("Le checkpoint local de Parakeet est introuvable.")
        if on_status:
            on_status("Chargement local de Parakeet...")

        nemo_asr = self._import_nemo()
        from nemo.utils import logging as nemo_logging

        nemo_logging.setLevel(logging.ERROR)
        self._model = nemo_asr.models.ASRModel.restore_from(
            restore_path=str(self._model_path),
            map_location="cpu",
        )
        self._model.freeze()
        self._release_loading_memory()

    def transcribe(self, audio_path: Path, language: str = "fr") -> str:
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

    def shutdown(self) -> None:
        self._model = None

    @staticmethod
    def _release_loading_memory() -> None:
        """Return temporary checkpoint allocations to the operating system."""
        import ctypes
        import gc

        gc.collect()
        try:
            allocator = ctypes.CDLL(None)
            malloc_trim = allocator.malloc_trim
        except (AttributeError, OSError):
            return
        malloc_trim(0)

    @staticmethod
    def _import_nemo() -> Any:
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise RuntimeError(
                "La dépendance Parakeet est absente. Exécutez "
                "'pip install -r requirements.txt' puis relancez T.A.R.S."
            ) from exc
        return nemo_asr
