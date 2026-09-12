from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from huggingface_hub import hf_hub_download


logger = logging.getLogger("TARS.Parakeet")


class ParakeetProvider:
    """Accès technique au checkpoint local de Parakeet uniquement."""

    REPOSITORY = "nvidia/parakeet-tdt-0.6b-v3"
    MODEL_FILE = "parakeet-tdt-0.6b-v3.nemo"

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._model_path = data_directory / self.MODEL_FILE
        self._model = None

    @property
    def model_available(self) -> bool:
        return self._model_path.is_file()

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        # Vérifie la dépendance avant de transférer un checkpoint volumineux.
        self._import_nemo()

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

        # restore_from() reçoit un .nemo local : aucune recherche de modèle ni
        # requête réseau n'est effectuée pendant l'utilisation normale.
        nemo_asr = self._import_nemo()
        self._model = nemo_asr.models.ASRModel.restore_from(
            restore_path=str(self._model_path),
            map_location="cpu",
        )
        self._model.eval()

    def transcribe(self, audio_path: Path) -> str:
        if self._model is None:
            raise RuntimeError("Parakeet n'est pas initialisé.")

        result = self._model.transcribe([str(audio_path)])[0]
        text = getattr(result, "text", result)
        return str(text).strip()

    def shutdown(self) -> None:
        self._model = None

    @staticmethod
    def _import_nemo():
        try:
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise RuntimeError(
                "La dépendance Parakeet est absente. Exécutez "
                "'pip install -r requirements.txt' puis relancez T.A.R.S."
            ) from exc
        return nemo_asr
