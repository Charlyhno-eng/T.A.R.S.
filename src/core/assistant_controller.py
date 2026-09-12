from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Property, Signal, Slot

from core.audio_recorder import AudioRecorder
from core.llm_service import LLMService
from core.responses import ResponseCatalog
from core.settings import Settings
from core.stt_service import STTService
from core.tts_service import TTSService


logger = logging.getLogger("TARS.Assistant")


class AssistantController(QObject):
    """QML entry point for local models and voice interaction."""

    stateChanged = Signal()
    statusChanged = Signal()
    modelsInstalledChanged = Signal()
    modelsReadyChanged = Signal()
    modelsLoadingChanged = Signal()
    modelsDownloadingChanged = Signal()
    transcriptChanged = Signal()
    responseChanged = Signal()
    audioPathChanged = Signal(str)
    languageChanged = Signal()

    ENGLISH_STATUS = {
        "Initialisation...": "Initializing...",
        "Chargement des modèles locaux...": "Loading local models...",
        "Modèles locaux non installés.": "Local models are not installed.",
        "Moteur vocal non installé.": "Voice engine is not installed.",
        "Chargement de Parakeet sur CPU...": "Loading Parakeet on CPU...",
        "Installation locale de Pocket TTS...": "Installing Pocket TTS locally...",
        "Chargement local de Pocket TTS...": "Loading Pocket TTS locally...",
        "Téléchargez d'abord les modèles locaux.": "Download the local models first.",
        "Chargement des modèles locaux en cours...": "Local models are loading...",
        "Parlez maintenant, puis relâchez le bouton.": "Speak now, then release the button.",
        "Transcription locale en cours...": "Transcribing locally...",
        "Transcription de votre message...": "Transcribing your message...",
        "Pocket TTS prêt. Chargement de Parakeet sur CPU...": "Pocket TTS is ready. Loading Parakeet on CPU...",
        "Modèles locaux prêts.": "Local models are ready.",
        "Installation locale de Parakeet...": "Installing Parakeet locally...",
        "Téléchargement de Parakeet (environ 2,5 Go)...": "Downloading Parakeet (about 2.5 GB)...",
        "Modèles installés. T.A.R.S. est utilisable hors ligne.": "Models installed. T.A.R.S. works offline.",
        "Échec du téléchargement des modèles locaux.": "Local model download failed.",
        "Échec du téléchargement du moteur vocal.": "Voice engine download failed.",
        "Je n'ai rien entendu. Réessayez.": "I didn't hear anything. Please try again.",
        "Réponse de T.A.R.S....": "T.A.R.S. response...",
        "Moteur vocal prêt.": "Voice engine is ready.",
        "Moteur vocal installé. T.A.R.S. fonctionne hors ligne.": "Voice engine installed. T.A.R.S. works offline.",
        "Moteur vocal installé et disponible hors ligne.": "Voice engine installed and available offline.",
        "Le moteur vocal n'est pas disponible.": "Voice engine is unavailable.",
        "Chargement du moteur vocal local...": "Loading local voice engine...",
        "Chargement du modèle Pocket TTS local...": "Loading local Pocket TTS model...",
        "Préparation de la voix locale...": "Preparing local voice...",
        "Téléchargement du moteur vocal...": "Downloading voice engine...",
        "Téléchargement du modèle Pocket TTS...": "Downloading Pocket TTS model...",
        "Téléchargement du tokenizer Pocket TTS...": "Downloading Pocket TTS tokenizer...",
        "Téléchargement de la voix Pocket TTS...": "Downloading Pocket TTS voice...",
        "Génération de la réponse vocale...": "Generating voice response...",
        "Erreur lors de la génération audio.": "Audio generation failed.",
        "Impossible de charger le moteur vocal local.": "Unable to load local voice engine.",
        "Chargement local de Parakeet...": "Loading Parakeet locally...",
        "Parakeet est prêt.": "Parakeet is ready.",
        "Parakeet est installé et disponible hors ligne.": "Parakeet is installed and available offline.",
        "Parakeet n'est pas disponible.": "Parakeet is unavailable.",
        "La langue ne peut être modifiée que lorsque T.A.R.S. est en veille.": "The language can only be changed while T.A.R.S. is on standby.",
        "Voix anglaise non installée. Cliquez sur télécharger.": "English voice is not installed. Click download.",
        "Voix française non installée. Cliquez sur télécharger.": "French voice is not installed. Click download.",
        "Installation locale de Needle 2...": "Installing Needle 2 locally...",
        "Téléchargement de Needle 2...": "Downloading Needle 2...",
        "Chargement local de Needle 2...": "Loading Needle 2 locally...",
        "Needle 2 est prêt.": "Needle 2 is ready.",
        "Needle 2 est installé et disponible hors ligne.": "Needle 2 is installed and available offline.",
        "Needle 2 n'est pas disponible.": "Needle 2 is unavailable.",
        "Analyse locale de votre demande...": "Analyzing your request locally...",
        "Erreur Needle 2": "Needle 2 error",
    }

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = Settings()
        self._response_catalog = ResponseCatalog()
        self._language = self._settings.language()
        self._state = "idle"
        self._status = "Initialisation..."
        self._transcript = ""
        self._response = ""
        self._tts_ready = False
        self._stt_ready = False
        self._llm_ready = False
        self._tts_loading = False
        self._stt_loading = False
        self._llm_loading = False
        self._models_downloading = False
        self._downloads_complete = False
        self._download_queue: list[str] = []
        self._started = False

        self._tts_service = TTSService(parent=self, language=self._language)
        self._stt_service = STTService(parent=self, language=self._language)
        self._llm_service = LLMService(parent=self, language=self._language)
        self._recorder = AudioRecorder(parent=self)

        self._tts_service.statusChanged.connect(self._set_status)
        self._tts_service.stateChanged.connect(self._on_tts_state_changed)
        self._tts_service.errorOccurred.connect(self._on_tts_error)
        self._tts_service.speechStarted.connect(
            lambda: self._set_state("speaking")
        )
        self._tts_service.speechFinished.connect(self._on_speech_finished)
        self._tts_service.installationFinished.connect(self._on_tts_installed)
        self._tts_service.installationFailed.connect(self._on_model_installation_failed)

        self._stt_service.statusChanged.connect(self._set_status)
        self._stt_service.stateChanged.connect(self._on_stt_state_changed)
        self._stt_service.errorOccurred.connect(self._on_stt_error)
        self._stt_service.transcriptionReady.connect(self._on_transcription_ready)
        self._stt_service.installationFinished.connect(self._on_stt_installed)
        self._stt_service.installationFailed.connect(
            self._on_model_installation_failed
        )

        self._llm_service.statusChanged.connect(self._set_status)
        self._llm_service.stateChanged.connect(self._on_llm_state_changed)
        self._llm_service.errorOccurred.connect(self._on_llm_error)
        self._llm_service.responseReady.connect(self._on_llm_response_ready)
        self._llm_service.installationFinished.connect(self._on_llm_installed)
        self._llm_service.installationFailed.connect(
            self._on_model_installation_failed
        )

    def start(self) -> None:
        """Start local model loading after the first UI event."""
        if self._started:
            return
        self._started = True
        if self.modelsInstalled:
            self._set_status("Chargement des modèles locaux...")
            self._stt_service.initialize_async()
            self._tts_service.initialize_async()
            self._llm_service.initialize_async()
        else:
            self._set_status("Modèles locaux non installés.")
            if self._tts_service.installed:
                self._tts_service.initialize_async()
            if self._stt_service.installed:
                self._stt_service.initialize_async()
            if self._llm_service.installed:
                self._llm_service.initialize_async()

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=modelsInstalledChanged)
    def modelsInstalled(self) -> bool:
        return (
            self._tts_service.installed
            and self._stt_service.installed
            and self._llm_service.installed
        )

    @Property(bool, notify=modelsReadyChanged)
    def modelsReady(self) -> bool:
        return self._tts_ready and self._stt_ready and self._llm_ready

    @Property(bool, notify=modelsLoadingChanged)
    def modelsLoading(self) -> bool:
        return self._tts_loading or self._stt_loading or self._llm_loading

    @Property(bool, notify=modelsDownloadingChanged)
    def modelsDownloading(self) -> bool:
        return self._models_downloading

    @Property(str, notify=transcriptChanged)
    def transcript(self) -> str:
        return self._transcript

    @Property(str, notify=responseChanged)
    def response(self) -> str:
        return self._response

    @Property(str, notify=languageChanged)
    def language(self) -> str:
        return self._language

    @Slot(str)
    def setLanguage(self, language: str) -> None:
        if language not in Settings.SUPPORTED_LANGUAGES or language == self._language:
            return
        if self._state != "idle" or self._models_downloading:
            self._set_status(
                "La langue ne peut être modifiée que lorsque T.A.R.S. est en veille."
            )
            return

        self._language = language
        self._settings.set_language(language)
        self.languageChanged.emit()
        self._transcript = ""
        self.transcriptChanged.emit()
        self._response = ""
        self.responseChanged.emit()

        try:
            self._tts_service.set_language(language)
            self._stt_service.set_language(language)
            self._llm_service.set_language(language)
        except RuntimeError as exc:
            self._set_status(str(exc))
            return

        self.modelsInstalledChanged.emit()
        if self._tts_service.installed:
            self._set_status("Chargement du moteur vocal local...")
            self._tts_service.initialize_async()
            self._stt_service.initialize_async()
            self._llm_service.initialize_async()
        else:
            self._set_status(
                "Voix anglaise non installée. Cliquez sur télécharger."
                if language == "en"
                else "Voix française non installée. Cliquez sur télécharger."
            )

    @Slot()
    def downloadModels(self) -> None:
        """Install all local providers through the single download button."""
        if self._models_downloading:
            return
        if self.modelsInstalled:
            if not self.modelsReady:
                self._set_status("Chargement des modèles locaux...")
                if not self._stt_service.initialized:
                    self._stt_service.initialize_async()
                if not self._tts_service.initialized:
                    self._tts_service.initialize_async()
                if not self._llm_service.initialized:
                    self._llm_service.initialize_async()
            return

        self._models_downloading = True
        self.modelsDownloadingChanged.emit()
        self._set_state("loading")
        self._download_queue = [
            name
            for name, installed in (
                ("tts", self._tts_service.installed),
                ("stt", self._stt_service.installed),
                ("llm", self._llm_service.installed),
            )
            if not installed
        ]
        self._start_next_model_download()

    @Slot()
    def startListening(self) -> None:
        if self._state != "idle":
            return
        if not self.modelsInstalled:
            self._set_status("Téléchargez d'abord les modèles locaux.")
            return
        if not self.modelsReady:
            self._set_status("Chargement des modèles locaux en cours...")
            return
        try:
            self._recorder.start()
        except Exception as exc:
            logger.exception("Impossible de démarrer l'enregistrement.")
            self._set_status(str(exc))
            return
        self._set_status("Parlez maintenant, puis relâchez le bouton.")
        self._set_state("listening")

    @Slot()
    def stopListening(self) -> None:
        if self._state != "listening":
            return
        try:
            audio_path = self._recorder.stop()
        except RuntimeError as exc:
            logger.warning("Enregistrement microphone ignoré : %s", exc)
            self._set_status(str(exc))
            self._set_state("idle")
            return
        except Exception as exc:
            logger.exception("Impossible de finaliser l'enregistrement.")
            self._set_status(str(exc))
            self._set_state("idle")
            return
        self._set_status("Transcription locale en cours...")
        self._set_state("thinking")
        self._stt_service.transcribe(audio_path)

    @Slot()
    def audioPlaybackFinished(self) -> None:
        self._tts_service.playback_finished()
        self._set_state("idle")

    def _on_tts_state_changed(self, state: str) -> None:
        loading_before = self.modelsLoading
        ready_before = self.modelsReady
        if state == "loading":
            self._tts_loading, self._tts_ready = True, False
        elif state == "ready":
            self._tts_loading, self._tts_ready = False, True
        elif state in ("error", "not_installed"):
            self._tts_loading, self._tts_ready = False, False
        if loading_before != self.modelsLoading:
            self.modelsLoadingChanged.emit()
        if ready_before != self.modelsReady:
            self.modelsReadyChanged.emit()

        self._update_models_ready_status(state)

    def _on_stt_state_changed(self, state: str) -> None:
        loading_before = self.modelsLoading
        ready_before = self.modelsReady
        if state == "loading":
            self._stt_loading, self._stt_ready = True, False
        elif state == "ready":
            self._stt_loading, self._stt_ready = False, True
        elif state in ("error", "not_installed"):
            self._stt_loading, self._stt_ready = False, False
        if loading_before != self.modelsLoading:
            self.modelsLoadingChanged.emit()
        if ready_before != self.modelsReady:
            self.modelsReadyChanged.emit()
        self._update_models_ready_status(state)

    def _on_llm_state_changed(self, state: str) -> None:
        loading_before = self.modelsLoading
        ready_before = self.modelsReady
        if state == "loading":
            self._llm_loading, self._llm_ready = True, False
        elif state == "ready":
            self._llm_loading, self._llm_ready = False, True
        elif state in ("error", "not_installed"):
            self._llm_loading, self._llm_ready = False, False
        if loading_before != self.modelsLoading:
            self.modelsLoadingChanged.emit()
        if ready_before != self.modelsReady:
            self.modelsReadyChanged.emit()
        self._update_models_ready_status(state)

    def _on_tts_installed(self) -> None:
        self.modelsInstalledChanged.emit()
        self._start_next_model_download()

    def _on_stt_installed(self) -> None:
        self.modelsInstalledChanged.emit()
        self._start_next_model_download()

    def _on_llm_installed(self) -> None:
        self.modelsInstalledChanged.emit()
        self._start_next_model_download()

    def _start_next_model_download(self) -> None:
        if not self._download_queue:
            self._finish_model_installation()
            return
        model = self._download_queue.pop(0)
        if model == "tts":
            self._set_status("Installation locale de Pocket TTS...")
            self._tts_service.download()
        elif model == "stt":
            self._set_status("Installation locale de Parakeet...")
            self._stt_service.download()
        else:
            self._set_status("Installation locale de Needle 2...")
            self._llm_service.download()

    def _finish_model_installation(self) -> None:
        self._downloads_complete = True
        self._set_status("Chargement des modèles locaux...")
        self._complete_model_loading()

    def _update_models_ready_status(self, state: str) -> None:
        if state != "ready" or not self.modelsReady:
            return
        if self._models_downloading:
            self._complete_model_loading()
            return
        self._set_status("Modèles locaux prêts.")

    def _complete_model_loading(self) -> None:
        if not self._downloads_complete or not self.modelsReady:
            return
        self._downloads_complete = False
        self._models_downloading = False
        self.modelsDownloadingChanged.emit()
        self._set_status("Modèles locaux prêts.")
        self._set_state("idle")

    def _on_model_installation_failed(self) -> None:
        self._models_downloading = False
        self._downloads_complete = False
        self._download_queue = []
        self.modelsDownloadingChanged.emit()
        self.modelsInstalledChanged.emit()
        self._set_status("Échec du téléchargement des modèles locaux.")
        self._set_state("idle")

    def _on_transcription_ready(self, text: str) -> None:
        self._transcript = text.strip()
        self.transcriptChanged.emit()
        if not self._transcript:
            self._set_status("Je n'ai rien entendu. Réessayez.")
            self._set_state("idle")
            return
        self._set_status("Analyse locale de votre demande...")
        self._llm_service.respond(self._transcript)

    def _on_llm_response_ready(self, text: str) -> None:
        self._response = text.strip()
        self.responseChanged.emit()
        if not self._response:
            fallback = self._response_catalog.responses(self._language).get(
                "unknown",
                "Aucune réponse locale n'est configurée.",
            )
            self._set_status(fallback)
            self._set_state("idle")
            return
        self._set_status("Réponse de T.A.R.S....")
        self._tts_service.speak(self._response)

    def _on_speech_finished(self, audio_path: str) -> None:
        self._set_status("Réponse de T.A.R.S....")
        self._set_state("speaking")
        self.audioPathChanged.emit(audio_path)

    def _on_tts_error(self, error: str) -> None:
        logger.error("Erreur Pocket TTS : %s", error)
        prefix = "Pocket TTS error" if self._language == "en" else "Erreur Pocket TTS"
        self._set_status(f"{prefix} : {error}")
        if self._state == "speaking":
            self._set_state("idle")

    def _on_stt_error(self, error: str) -> None:
        logger.error("Erreur Parakeet : %s", error)
        prefix = "Parakeet error" if self._language == "en" else "Erreur Parakeet"
        self._set_status(f"{prefix} : {error}")
        if self._state == "thinking":
            self._set_state("idle")

    def _on_llm_error(self, error: str) -> None:
        logger.error("Erreur Needle 2 : %s", error)
        prefix = "Needle 2 error" if self._language == "en" else "Erreur Needle 2"
        self._set_status(f"{prefix} : {error}")
        if self._state == "thinking":
            self._set_state("idle")

    def _set_state(self, value: str) -> None:
        if value != self._state:
            self._state = value
            self.stateChanged.emit()

    def _set_status(self, value: str) -> None:
        if self._language == "en":
            value = self.ENGLISH_STATUS.get(value, value)
        if value != self._status:
            self._status = value
            self.statusChanged.emit()

    def shutdown(self) -> None:
        if self._recorder.recording:
            try:
                self._recorder.cancel()
            except Exception:
                logger.exception("Erreur lors de l'arrêt du microphone.")
        self._tts_service.shutdown()
        self._stt_service.shutdown()
        self._llm_service.shutdown()
