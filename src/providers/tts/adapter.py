from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable

from providers.tts.pocket_tts import PocketTTSProvider


logger = logging.getLogger("TARS.TTSAdapter")


class TTSAdapter:
    """Expose a stable offline interface to Pocket TTS."""

    def __init__(self, language: str = "en") -> None:
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
        self._language = language

    @property
    def installed(self) -> bool:
        """Return whether the selected voice is fully installed."""
        return (
            self._installation_marker.exists()
            and self._provider.resources_available(self._language)
        )

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        if language == self._language:
            return
        if language not in PocketTTSProvider.LANGUAGES:
            raise ValueError(f"Langue non prise en charge : {language}")
        self._provider.shutdown()
        self._language = language

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Load the selected engine from local resources only."""

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

        self._provider.load(self._language, on_status=on_status)

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Download and prepare resources after an explicit user action."""

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
                self._language,
                on_status=on_status,
            )

            self._provider.load(self._language, on_status=on_status)

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
            "language": self._language,
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
