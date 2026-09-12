from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable


logger = logging.getLogger("TARS.PocketTTS")


class PocketTTSProvider:
    """Technical local access to Pocket TTS for French and English."""

    PUBLIC_REPOSITORY = "kyutai/pocket-tts-without-voice-cloning"
    WEIGHTS_REVISION = "d29db7978e464fb90cb3359ee0c69a273b9142cc"
    VOICE_REVISION = "e81d79e8194ad4c7ce879c87a4258ef20cbf2487"

    LANGUAGES = {
        "fr": {
            "pocket_language": "french_24l",
            "voice": "estelle",
        },
        "en": {
            "pocket_language": "english",
            "voice": "alba",
        },
    }

    def __init__(self, data_directory: Path) -> None:
        self._data_directory = data_directory
        self._resources_directory = data_directory / "resources"
        self._model: Any | None = None
        self._voice_state = None
        self._loaded_language: str | None = None

    def resources_available(self, language: str) -> bool:
        return all(
            path.is_file()
            for path in (
                self._model_path(language),
                self._tokenizer_path(language),
                self._voice_path(language),
                self._config_path(language),
            )
        )

    def download(
        self,
        language: str,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        from huggingface_hub import hf_hub_download

        info = self._language_info(language)
        pocket_language = info["pocket_language"]
        self._resources_directory.mkdir(parents=True, exist_ok=True)

        files = (
            (
                "Téléchargement du modèle Pocket TTS...",
                f"languages/{pocket_language}/model.safetensors",
                self.WEIGHTS_REVISION,
            ),
            (
                "Téléchargement du tokenizer Pocket TTS...",
                f"languages/{pocket_language}/tokenizer.model",
                self.WEIGHTS_REVISION,
            ),
            (
                "Téléchargement de la voix Pocket TTS...",
                f"languages/{pocket_language}/embeddings/{info['voice']}.safetensors",
                self.VOICE_REVISION,
            ),
        )
        for message, filename, revision in files:
            if on_status:
                on_status(message)
            hf_hub_download(
                repo_id=self.PUBLIC_REPOSITORY,
                filename=filename,
                revision=revision,
                local_dir=str(self._resources_directory),
            )
        self._write_local_config(language)

    def load(
        self,
        language: str,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        if self.initialized and self._loaded_language == language:
            return
        self.shutdown()
        if not self.resources_available(language):
            raise RuntimeError(
                "Les fichiers locaux de Pocket TTS pour cette langue sont incomplets."
            )
        if on_status:
            on_status("Chargement du modèle Pocket TTS local...")
        from pocket_tts import TTSModel

        self._model = TTSModel.load_model(config=self._config_path(language))
        if on_status:
            on_status("Préparation de la voix locale...")
        self._voice_state = self._model.get_state_for_audio_prompt(
            self._voice_path(language)
        )
        self._loaded_language = language
        if on_status:
            on_status("Moteur vocal prêt.")

    @property
    def initialized(self) -> bool:
        return self._model is not None and self._voice_state is not None

    def generate(self, text: str, output_path: Path) -> Path:
        if not self.initialized or self._model is None:
            raise RuntimeError("Pocket TTS n'est pas initialisé.")
        import scipy.io.wavfile
        import torch

        torch.set_num_threads(1)
        audio = self._model.generate_audio(self._voice_state, text.strip())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        scipy.io.wavfile.write(
            str(output_path), self._model.sample_rate, audio.cpu().numpy()
        )
        return output_path

    def shutdown(self) -> None:
        self._voice_state = None
        self._model = None
        self._loaded_language = None

    def _language_info(self, language: str) -> dict[str, str]:
        try:
            return self.LANGUAGES[language]
        except KeyError as exc:
            raise ValueError(f"Langue Pocket TTS non prise en charge : {language}") from exc

    def _model_path(self, language: str) -> Path:
        name = self._language_info(language)["pocket_language"]
        return self._resources_directory / "languages" / name / "model.safetensors"

    def _tokenizer_path(self, language: str) -> Path:
        name = self._language_info(language)["pocket_language"]
        return self._resources_directory / "languages" / name / "tokenizer.model"

    def _voice_path(self, language: str) -> Path:
        info = self._language_info(language)
        return (
            self._resources_directory / "languages" / info["pocket_language"]
            / "embeddings" / f"{info['voice']}.safetensors"
        )

    def _config_path(self, language: str) -> Path:
        return self._data_directory / f"pocket_tts_{language}.yaml"

    def _write_local_config(self, language: str) -> None:
        import pocket_tts
        import yaml

        pocket_language = self._language_info(language)["pocket_language"]
        source = (
            Path(pocket_tts.__file__).resolve().parent / "config"
            / f"{pocket_language}.yaml"
        )
        config = yaml.safe_load(source.read_text(encoding="utf-8"))
        config["weights_path"] = str(self._model_path(language))
        config["weights_path_without_voice_cloning"] = str(self._model_path(language))
        config["flow_lm"]["lookup_table"]["tokenizer_path"] = str(
            self._tokenizer_path(language)
        )
        self._config_path(language).write_text(
            yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
