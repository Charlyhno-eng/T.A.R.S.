from __future__ import annotations

from pathlib import Path
from typing import Callable

import scipy.io.wavfile
from pocket_tts import TTSModel


class PocketTTS:
    """
    Intégration minimale avec Kyutai Pocket TTS.

    Ce fichier ne contient aucune logique métier T.A.R.S.
    Il sert uniquement à communiquer avec la librairie Pocket TTS.
    """

    LANGUAGE = "french_24l"
    VOICE = "estelle"

    def __init__(self) -> None:
        self._model: TTSModel | None = None
        self._voice_state = None

    @property
    def sample_rate(self) -> int:
        if self._model is None:
            raise RuntimeError("Pocket TTS n'est pas initialisé.")

        return self._model.sample_rate

    def initialize(self, on_status: Callable[[str], None] | None = None) -> None:
        """
        Charge le modèle français et la voix prédéfinie Estelle.

        Important :
        on utilise ici une voix catalogue officielle de Pocket TTS.
        Aucun voice cloning n'est demandé.
        """

        if self._model is not None and self._voice_state is not None:
            return

        if on_status:
            on_status("Chargement du modèle Pocket TTS...")

        # Ne surtout pas fournir de checkpoint de voice cloning.
        self._model = TTSModel.load_model(
            language=self.LANGUAGE,
        )

        if on_status:
            on_status(
                f"Chargement de la voix française « {self.VOICE} »..."
            )

        # "estelle" est une voix prédéfinie de Pocket TTS.
        #
        # Pocket TTS choisit alors l'état vocal catalogue correspondant
        # au modèle français au lieu de tenter de cloner une voix.
        self._voice_state = self._model.get_state_for_audio_prompt(
            self.VOICE
        )

        if on_status:
            on_status("Pocket TTS prêt.")

    def generate(self, text: str, output_path: Path) -> Path:
        """
        Génère un fichier WAV avec Pocket TTS.
        """

        if self._model is None or self._voice_state is None:
            raise RuntimeError("Pocket TTS n'est pas initialisé.")

        text = text.strip()

        if not text:
            raise ValueError("Le texte à synthétiser est vide.")

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        audio = self._model.generate_audio(
            self._voice_state,
            text,
        )

        scipy.io.wavfile.write(
            str(output_path),
            self._model.sample_rate,
            audio.numpy(),
        )

        return output_path

    def shutdown(self) -> None:
        """
        Libère les références vers le modèle Pocket TTS.
        """

        self._voice_state = None
        self._model = None
