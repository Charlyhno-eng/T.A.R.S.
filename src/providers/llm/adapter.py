from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from providers.llm.needle import NeedleProvider


class LLMAdapter:
    """Stable interface between T.A.R.S. and Needle 2."""

    def __init__(
        self,
        agent_definitions: tuple[tuple[str, str], ...] = (),
    ) -> None:
        self._data_directory = Path.home() / ".tars" / "llm"
        self._installation_marker = self._data_directory / "needle2_installed.json"
        self._provider = NeedleProvider(
            data_directory=self._data_directory,
            agent_definitions=agent_definitions,
        )

    @property
    def installed(self) -> bool:
        return self._installation_marker.exists() and self._provider.model_available

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        if not self.installed:
            raise RuntimeError(
                "Needle 2 n'est pas installé. Cliquez sur le bouton de téléchargement."
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

    def select_route(self, text: str) -> str:
        return self._provider.select_route(text=text)

    def shutdown(self) -> None:
        self._provider.shutdown()

    def _write_installation_marker(self) -> None:
        temporary_file = self._installation_marker.with_suffix(".tmp")
        temporary_file.write_text(
            json.dumps(
                {"provider": "needle2", "offline": True}, indent=2),
            encoding="utf-8",
        )
        temporary_file.replace(self._installation_marker)
