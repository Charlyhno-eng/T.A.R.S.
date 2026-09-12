from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from providers.tts.pocket_tts import PocketTTSProvider


logger = logging.getLogger("TARS.TTSAdapter")


class TTSAdapter:
    """
    Adaptateur TTS de T.A.R.S.

    Cette classe permet de découpler T.A.R.S. de Pocket TTS.

    Elle gère :
    - l'installation initiale du moteur ;
    - le chargement hors ligne ;
    - la génération audio ;
    - l'état d'installation.

    Le reste de l'application ne connaît pas Pocket TTS.
    """

    MODEL_LANGUAGE = "french_24l"
    MODEL_VOICE = "estelle"

    def __init__(self) -> None:
        self._data_directory = (
            Path.home()
            / ".tars"
            / "tts"
        )

        self._installation_marker = (
            self._data_directory
            / "pocket_tts_installed.json"
        )

        self._provider = PocketTTSProvider(
            data_directory=self._data_directory,
        )

    @property
    def installed(self) -> bool:
        """
        Indique si T.A.R.S. a déjà effectué une installation complète
        du moteur vocal.
        """
        return (
            self._installation_marker.exists()
            and self._provider.resources_available
        )

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """
        Charge le moteur depuis les ressources déjà téléchargées.

        Cette méthode est utilisée au démarrage normal de T.A.R.S.

        Elle ne doit pas déclencher de téléchargement Internet.
        """

        if not self.installed:
            raise RuntimeError(
                "Le moteur vocal n'est pas installé. "
                "Cliquez sur le bouton de téléchargement."
            )

        logger.info(
            "[T.A.R.S.][TTS] Chargement hors ligne."
        )

        if on_status:
            on_status(
                "Chargement du moteur vocal local..."
            )

        # Le provider reçoit uniquement des chemins locaux préparés lors de
        # download(). Il ne peut donc pas interroger Hugging Face ici.
        self._provider.load(on_status=on_status)

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """
        Télécharge et prépare toutes les ressources nécessaires.

        Cette méthode est appelée explicitement par l'utilisateur
        via le bouton de téléchargement de l'interface.
        """

        logger.info(
            "[T.A.R.S.][TTS] Installation du moteur vocal."
        )

        if on_status:
            on_status(
                "Téléchargement du moteur vocal..."
            )

        try:
            self._provider.shutdown()
            self._provider.download(
                on_status=on_status,
            )

            self._provider.load(on_status=on_status)

            self._write_installation_marker()

            logger.info(
                "[T.A.R.S.][TTS] Installation terminée."
            )

            if on_status:
                on_status(
                    "Moteur vocal installé et disponible hors ligne."
                )

        except Exception:
            logger.exception(
                "[T.A.R.S.][TTS] Échec de l'installation."
            )

            raise

    def _write_installation_marker(self) -> None:
        data = {
            "provider": "pocket-tts",
            "language": self.MODEL_LANGUAGE,
            "voice": self.MODEL_VOICE,
            "offline": True,
        }

        temporary_file = (
            self._installation_marker.with_suffix(
                ".tmp"
            )
        )

        temporary_file.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_file.replace(
            self._installation_marker
        )

    def generate(
        self,
        text: str,
        output_path: Path,
    ) -> Path:
        return self._provider.generate(
            text=text,
            output_path=output_path,
        )

    def shutdown(self) -> None:
        self._provider.shutdown()
