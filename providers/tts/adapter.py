from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Callable


logger = logging.getLogger("TARS.TTS")


class TTSAdapter:
    """
    Adaptateur TTS de T.A.R.S.

    C'est volontairement le SEUL fichier de l'application qui connaît
    l'implémentation concrète Pocket TTS.

    Si demain Pocket TTS est remplacé par :
        - Piper
        - Coqui TTS
        - Kokoro
        - une API distante
        - autre chose

    seul cet adapter devra être modifié.

    Le reste de l'application communique uniquement avec :
        initialize()
        generate()
        shutdown()
    """

    def __init__(self) -> None:
        self._provider = None

    # ==================================================================
    # Provider
    # ==================================================================

    def _load_provider(self):
        """
        Charge dynamiquement pocket-tts.py.

        Le nom du fichier contient un tiret, donc il n'est pas possible
        de faire un import Python classique avec `import pocket-tts`.
        """

        provider_path = (
            Path(__file__).resolve().parent
            / "pocket-tts.py"
        )

        if not provider_path.exists():
            raise FileNotFoundError(
                f"Provider TTS introuvable : {provider_path}"
            )

        spec = importlib.util.spec_from_file_location(
            "tars_pocket_tts_provider",
            provider_path,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                "Impossible de charger le provider Pocket TTS."
            )

        module = importlib.util.module_from_spec(
            spec
        )

        spec.loader.exec_module(module)

        provider_class = getattr(
            module,
            "PocketTTS",
            None,
        )

        if provider_class is None:
            raise ImportError(
                "pocket-tts.py doit exposer une classe "
                "'PocketTTS'."
            )

        return provider_class()

    # ==================================================================
    # API publique
    # ==================================================================

    def initialize(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialise Pocket TTS.
        """

        if self._provider is not None:
            return

        logger.info(
            "[T.A.R.S.][TTS] Chargement du provider Pocket TTS..."
        )

        self._provider = self._load_provider()

        self._provider.initialize(
            on_status=on_status,
        )

    def generate(
        self,
        text: str,
        output_path: Path,
    ) -> Path:
        """
        Demande au provider de générer un fichier WAV.
        """

        if self._provider is None:
            raise RuntimeError(
                "Le provider TTS n'est pas initialisé."
            )

        return self._provider.generate(
            text=text,
            output_path=output_path,
        )

    def shutdown(self) -> None:
        """
        Arrête le provider.
        """

        if self._provider is None:
            return

        try:
            self._provider.shutdown()

        finally:
            self._provider = None
