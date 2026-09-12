from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Property, Signal, Slot

from core.audio_recorder import AudioRecorder
from core.stt_service import STTService
from core.tts_service import TTSService


logger = logging.getLogger("TARS.Assistant")


class AssistantController(QObject):
    """Point d'entrée QML pour les modèles locaux et l'interaction vocale."""

    stateChanged = Signal()
    statusChanged = Signal()
    modelsInstalledChanged = Signal()
    modelsReadyChanged = Signal()
    modelsLoadingChanged = Signal()
    modelsDownloadingChanged = Signal()
    transcriptChanged = Signal()
    audioPathChanged = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._status = "Initialisation..."
        self._transcript = ""
        self._tts_ready = False
        self._stt_ready = False
        self._tts_loading = False
        self._stt_loading = False
        self._models_downloading = False
        self._download_stt_after_tts = False
        self._startup_stt_pending = False

        self._tts_service = TTSService(parent=self)
        self._stt_service = STTService(parent=self)
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
        self._stt_service.installationFailed.connect(self._on_model_installation_failed)

        if self.modelsInstalled:
            self._set_status("Chargement des modèles locaux...")
            # Le chargement est volontairement séquentiel : Parakeet et le
            # Pocket TTS français mobilisent tous deux beaucoup de RAM sur CPU.
            self._startup_stt_pending = True
            self._tts_service.initialize_async()
        else:
            self._set_status("Modèles vocaux non installés.")

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=modelsInstalledChanged)
    def modelsInstalled(self) -> bool:
        return self._tts_service.installed and self._stt_service.installed

    @Property(bool, notify=modelsReadyChanged)
    def modelsReady(self) -> bool:
        return self._tts_ready and self._stt_ready

    @Property(bool, notify=modelsLoadingChanged)
    def modelsLoading(self) -> bool:
        return self._tts_loading or self._stt_loading

    @Property(bool, notify=modelsDownloadingChanged)
    def modelsDownloading(self) -> bool:
        return self._models_downloading

    @Property(str, notify=transcriptChanged)
    def transcript(self) -> str:
        return self._transcript

    @Slot()
    def downloadModels(self) -> None:
        """Installe successivement TTS puis STT depuis le bouton unique."""
        if self._models_downloading:
            return
        if self.modelsInstalled:
            if not self.modelsReady:
                if self._tts_service.initialized:
                    self._set_status("Chargement de Parakeet sur CPU...")
                    self._stt_service.initialize_async()
                else:
                    self._startup_stt_pending = True
                    self._tts_service.initialize_async()
            return

        self._models_downloading = True
        self.modelsDownloadingChanged.emit()
        self._set_state("loading")
        self._download_stt_after_tts = not self._stt_service.installed

        if not self._tts_service.installed:
            self._set_status("Installation locale de Pocket TTS...")
            self._tts_service.download()
        elif not self._tts_service.initialized:
            # Une précédente installation a pu s'arrêter après Pocket TTS.
            # Chargeons-le avant de poursuivre avec Parakeet.
            self._set_status("Chargement local de Pocket TTS...")
            self._tts_service.initialize_async()
        elif self._download_stt_after_tts:
            self._start_stt_download()
        else:
            self._finish_model_installation()

    @Slot()
    def startListening(self) -> None:
        if self._state != "idle":
            return
        if not self.modelsInstalled:
            self._set_status("Téléchargez d'abord les modèles vocaux.")
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
        if state == "loading":
            self._tts_loading, self._tts_ready = True, False
        elif state == "ready":
            self._tts_loading, self._tts_ready = False, True
        elif state in ("error", "not_installed"):
            self._tts_loading, self._tts_ready = False, False
            self._startup_stt_pending = False
        self.modelsLoadingChanged.emit()
        self.modelsReadyChanged.emit()
        self.modelsInstalledChanged.emit()

        if state == "ready" and self._startup_stt_pending:
            self._startup_stt_pending = False
            self._set_status(
                "Pocket TTS prêt. Chargement de Parakeet sur CPU..."
            )
            self._stt_service.initialize_async()
        elif (
            state == "ready"
            and self._models_downloading
            and self._download_stt_after_tts
            and not self._stt_service.installed
        ):
            self._start_stt_download()

    def _on_stt_state_changed(self, state: str) -> None:
        if state == "loading":
            self._stt_loading, self._stt_ready = True, False
        elif state == "ready":
            self._stt_loading, self._stt_ready = False, True
        elif state in ("error", "not_installed"):
            self._stt_loading, self._stt_ready = False, False
        self.modelsLoadingChanged.emit()
        self.modelsReadyChanged.emit()
        self.modelsInstalledChanged.emit()
        if state == "ready" and self.modelsReady:
            self._set_status("Modèles vocaux locaux prêts.")

    def _on_tts_installed(self) -> None:
        self.modelsInstalledChanged.emit()
        if self._download_stt_after_tts:
            self._start_stt_download()
        else:
            self._finish_model_installation()

    def _start_stt_download(self) -> None:
        self._download_stt_after_tts = False
        self._set_status("Installation locale de Parakeet...")
        self._stt_service.download()

    def _on_stt_installed(self) -> None:
        self.modelsInstalledChanged.emit()
        self._finish_model_installation()

    def _finish_model_installation(self) -> None:
        self._models_downloading = False
        self.modelsDownloadingChanged.emit()
        self.modelsInstalledChanged.emit()
        self._set_status("Modèles installés. T.A.R.S. est utilisable hors ligne.")
        self._set_state("idle")

    def _on_model_installation_failed(self) -> None:
        self._models_downloading = False
        self._download_stt_after_tts = False
        self.modelsDownloadingChanged.emit()
        self.modelsInstalledChanged.emit()
        self._set_status("Échec du téléchargement des modèles vocaux.")
        self._set_state("idle")

    def _on_transcription_ready(self, text: str) -> None:
        self._transcript = text.strip()
        self.transcriptChanged.emit()
        if not self._transcript:
            self._set_status("Je n'ai rien entendu. Réessayez.")
            self._set_state("idle")
            return
        self._set_status(f"Vous avez dit : {self._transcript}")
        self._tts_service.speak(self._transcript)

    def _on_speech_finished(self, audio_path: str) -> None:
        self._set_status("Répétition de votre message...")
        self._set_state("speaking")
        self.audioPathChanged.emit(audio_path)

    def _on_tts_error(self, error: str) -> None:
        logger.error("Erreur Pocket TTS : %s", error)
        self._set_status(f"Erreur Pocket TTS : {error}")
        if self._state == "speaking":
            self._set_state("idle")

    def _on_stt_error(self, error: str) -> None:
        logger.error("Erreur Parakeet : %s", error)
        self._set_status(f"Erreur Parakeet : {error}")
        if self._state == "thinking":
            self._set_state("idle")

    def _set_state(self, value: str) -> None:
        if value != self._state:
            self._state = value
            self.stateChanged.emit()

    def _set_status(self, value: str) -> None:
        if value != self._status:
            self._status = value
            self.statusChanged.emit()

    def shutdown(self) -> None:
        if self._recorder.recording:
            try:
                self._recorder.stop()
            except Exception:
                logger.exception("Erreur lors de l'arrêt du microphone.")
        self._tts_service.shutdown()
        self._stt_service.shutdown()
