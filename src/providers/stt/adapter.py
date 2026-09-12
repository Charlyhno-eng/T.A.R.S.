from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from providers.stt.parakeet import ParakeetProvider


class STTAdapter:
    """Interface stable entre T.A.R.S. et Parakeet."""

    def __init__(self) -> None:
        self._data_directory = Path.home() / ".tars" / "stt"
        self._installation_marker = (
            self._data_directory / "parakeet_installed.json"
        )
        self._provider = ParakeetProvider(
            data_directory=self._data_directory,
        )

    @property
    def installed(self) -> bool:
        return (
            self._installation_marker.exists()
            and self._provider.model_available
        )

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        if not self.installed:
            raise RuntimeError(
                "Parakeet n'est pas installé. Cliquez sur le bouton "
                "de téléchargement."
            )
        self._provider.load(on_status=on_status)

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self._provider.shutdown()
        self._provider.download(on_status=on_status)
        self._provider.load(on_status=on_status)
        self._write_installation_marker()

    def transcribe(self, audio_path: Path) -> str:
        return self._provider.transcribe(audio_path)

    def shutdown(self) -> None:
        self._provider.shutdown()

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
