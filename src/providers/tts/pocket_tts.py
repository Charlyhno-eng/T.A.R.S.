from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import scipy.io.wavfile

from pocket_tts import TTSModel


logger = logging.getLogger("TARS.PocketTTS")


class PocketTTSProvider:
    """
    Interface technique directe avec Kyutai Pocket TTS.

    Ce fichier est exclusivement consacré à Pocket TTS.

    Responsabilités :
    - charger le modèle ;
    - préparer la voix ;
    - générer les fichiers WAV ;
    - libérer le modèle.

    Aucune logique métier de T.A.R.S. ne doit être ajoutée ici.
    """

    LANGUAGE = "french_24l"
    VOICE = "estelle"

    def __init__(self) -> None:
        self._model: TTSModel | None = None
        self._voice_state = None

    @property
    def initialized(self) -> bool:
        return (
            self._model is not None
            and self._voice_state is not None
        )

    def load(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """
        Charge Pocket TTS et prépare la voix française Estelle.

        Le comportement réseau/hors-ligne est contrôlé par l'adaptateur.
        Ce provider ne décide pas quand Internet doit être utilisé.
        """

        if self.initialized:
            return

        if on_status:
            on_status(
                "Chargement du modèle Pocket TTS..."
            )

        logger.info(
            "[Pocket TTS] Chargement du modèle : %s",
            self.LANGUAGE,
        )

        self._model = TTSModel.load_model(
            language=self.LANGUAGE,
        )

        if on_status:
            on_status(
                "Préparation de la voix française..."
            )

        logger.info(
            "[Pocket TTS] Préparation de la voix : %s",
            self.VOICE,
        )

        self._voice_state = (
            self._model.get_state_for_audio_prompt(
                self.VOICE,
            )
        )

        logger.info(
            "[Pocket TTS] Modèle et voix prêts."
        )

        if on_status:
            on_status(
                "Moteur vocal prêt."
            )

    def generate(
        self,
        text: str,
        output_path: Path,
    ) -> Path:
        """
        Génère un fichier WAV à partir du texte fourni.
        """

        if not self.initialized:
            raise RuntimeError(
                "Pocket TTS n'est pas initialisé."
            )

        text = text.strip()

        if not text:
            raise ValueError(
                "Le texte à synthétiser est vide."
            )

        if self._model is None:
            raise RuntimeError(
                "Le modèle Pocket TTS n'est pas chargé."
            )

        if self._voice_state is None:
            raise RuntimeError(
                "La voix Pocket TTS n'est pas préparée."
            )

        logger.info(
            "[Pocket TTS] Génération audio : %s",
            text,
        )

        audio = self._model.generate_audio(
            self._voice_state,
            text,
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        scipy.io.wavfile.write(
            str(output_path),
            self._model.sample_rate,
            audio.cpu().numpy(),
        )

        logger.info(
            "[Pocket TTS] Audio écrit : %s",
            output_path,
        )

        return output_path

    def shutdown(self) -> None:
        """
        Libère les ressources Pocket TTS.
        """

        logger.info(
            "[Pocket TTS] Arrêt du moteur."
        )

        self._voice_state = None
        self._model = None
