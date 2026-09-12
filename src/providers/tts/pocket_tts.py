from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

import scipy.io.wavfile
import yaml
from huggingface_hub import hf_hub_download

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

    # Les poids avec clonage vocal sont gated par Kyutai et exigent un compte
    # Hugging Face. Cette version française publique est celle utilisée par
    # Pocket TTS comme solution de repli officielle.
    MODEL_REPOSITORY = "kyutai/pocket-tts-without-voice-cloning"
    MODEL_REVISION = "d29db7978e464fb90cb3359ee0c69a273b9142cc"
    MODEL_FILE = "languages/french_24l/model.safetensors"

    ASSETS_REPOSITORY = "kyutai/pocket-tts-without-voice-cloning"
    ASSETS_REVISION = "d29db7978e464fb90cb3359ee0c69a273b9142cc"
    TOKENIZER_FILE = "languages/french_24l/tokenizer.model"

    VOICE_REPOSITORY = "kyutai/pocket-tts-without-voice-cloning"
    VOICE_REVISION = "e81d79e8194ad4c7ce879c87a4258ef20cbf2487"
    VOICE_FILE = "languages/french_24l/embeddings/estelle.safetensors"

    def __init__(
        self,
        data_directory: Path,
    ) -> None:
        self._model: TTSModel | None = None
        self._voice_state = None
        self._data_directory = data_directory
        self._resources_directory = data_directory / "resources"
        self._config_path = data_directory / "pocket_tts_french.yaml"

    @property
    def resources_available(self) -> bool:
        return all(
            path.is_file()
            for path in (
                self._model_path,
                self._tokenizer_path,
                self._voice_path,
                self._config_path,
            )
        )

    @property
    def _model_path(self) -> Path:
        return self._resources_directory / self.MODEL_FILE

    @property
    def _tokenizer_path(self) -> Path:
        return self._resources_directory / self.TOKENIZER_FILE

    @property
    def _voice_path(self) -> Path:
        return self._resources_directory / self.VOICE_FILE

    def download(
        self,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        """Télécharge les trois ressources puis crée la config locale."""

        self._resources_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        downloads = (
            (
                "Téléchargement du modèle Pocket TTS...",
                self.MODEL_REPOSITORY,
                self.MODEL_FILE,
                self.MODEL_REVISION,
            ),
            (
                "Téléchargement du tokenizer Pocket TTS...",
                self.ASSETS_REPOSITORY,
                self.TOKENIZER_FILE,
                self.ASSETS_REVISION,
            ),
            (
                "Téléchargement de la voix française Estelle...",
                self.VOICE_REPOSITORY,
                self.VOICE_FILE,
                self.VOICE_REVISION,
            ),
        )

        for message, repository, filename, revision in downloads:
            if on_status:
                on_status(message)

            hf_hub_download(
                repo_id=repository,
                filename=filename,
                revision=revision,
                local_dir=str(self._resources_directory),
            )

        self._write_local_config()

    def _write_local_config(self) -> None:
        """Remplace les URL hf:// du package par des chemins absolus locaux."""

        # Le fichier de configuration appartient au paquet pocket-tts. Ne pas
        # l'éditer : T.A.R.S. écrit sa copie autonome dans ~/.tars/tts.
        import pocket_tts

        package_config = (
            Path(pocket_tts.__file__).resolve().parent
            / "config"
            / "french_24l.yaml"
        )

        config = yaml.safe_load(
            package_config.read_text(encoding="utf-8")
        )
        config["weights_path"] = str(self._model_path)
        config["weights_path_without_voice_cloning"] = str(
            self._model_path
        )
        config["flow_lm"]["lookup_table"]["tokenizer_path"] = str(
            self._tokenizer_path
        )

        self._config_path.write_text(
            yaml.safe_dump(
                config,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

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

        if not self.resources_available:
            raise RuntimeError(
                "Les fichiers locaux de Pocket TTS sont incomplets. "
                "Relancez le téléchargement des modèles."
            )

        self._model = TTSModel.load_model(
            config=self._config_path,
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
                self._voice_path,
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
