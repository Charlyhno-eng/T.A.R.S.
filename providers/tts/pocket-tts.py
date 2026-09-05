from __future__ import annotations
import tempfile
from pathlib import Path
import scipy.io.wavfile
from pocket_tts import TTSModel
from .adapter import TTSAdapter


class PocketTTSProvider(TTSAdapter):
    """
    Provider TTS basé sur Kyutai Pocket TTS.

    Modèle :
        french_24l

    Voix :
        estelle

    Le modèle et l'état de la voix sont conservés en mémoire
    afin d'éviter de les recharger à chaque phrase.
    """

    LANGUAGE = "french_24l"
    VOICE = "estelle"

    def __init__(self, output_directory: Path | None = None) -> None:
        self._model: TTSModel | None = None
        self._voice_state = None

        if output_directory is None:
            output_directory = Path(tempfile.gettempdir()) / "tars_tts"

        self.output_directory = Path(output_directory)
        self.output_directory.mkdir(parents=True, exist_ok=True)

    def _load_model(self) -> None:
        """
        Charge le modèle français et la voix Estelle.

        Cette méthode n'est exécutée qu'une seule fois.
        """

        if self._model is not None and self._voice_state is not None:
            return

        print("[T.A.R.S.][TTS] Chargement de Pocket TTS...")
        print(f"[T.A.R.S.][TTS] Langue : {self.LANGUAGE}")
        print(f"[T.A.R.S.][TTS] Voix : {self.VOICE}")

        self._model = TTSModel.load_model(
            language=self.LANGUAGE,
        )

        self._voice_state = self._model.get_state_for_audio_prompt(
            self.VOICE
        )

        print("[T.A.R.S.][TTS] Pocket TTS prêt.")

    def speak(self, text: str) -> Path:
        """
        Génère un fichier WAV à partir du texte fourni.
        """

        if not text or not text.strip():
            raise ValueError("Le texte TTS ne peut pas être vide.")

        self._load_model()

        if self._model is None or self._voice_state is None:
            raise RuntimeError("Pocket TTS n'a pas pu être initialisé.")

        print(f"[T.A.R.S.][TTS] Génération : {text}")

        audio = self._model.generate_audio(
            self._voice_state,
            text.strip(),
        )

        output_path = self.output_directory / "tars_response.wav"

        scipy.io.wavfile.write(
            str(output_path),
            self._model.sample_rate,
            audio.numpy(),
        )

        print(f"[T.A.R.S.][TTS] Audio généré : {output_path}")

        return output_path

    def close(self) -> None:
        """
        Libère les références vers le modèle.
        """

        self._voice_state = None
        self._model = None

        print("[T.A.R.S.][TTS] Provider arrêté.")
