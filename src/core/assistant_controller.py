from __future__ import annotations

import logging

from PySide6.QtCore import (
    QObject,
    Property,
    Signal,
    Slot,
)

from core.tts_service import TTSService


logger = logging.getLogger("TARS.Assistant")


class AssistantController(QObject):
    """
    Contrôleur principal de T.A.R.S.

    QML communique uniquement avec cette classe.
    """

    stateChanged = Signal()
    statusChanged = Signal()

    ttsReadyChanged = Signal()
    ttsLoadingChanged = Signal()
    ttsDownloadingChanged = Signal()
    ttsInstalledChanged = Signal()

    ttsErrorChanged = Signal()
    audioPathChanged = Signal()

    GREETING = (
        "Bonjour utilisateur, je suis votre assistant "
        "T.A.R.S., comment puis-je vous aider aujourd'hui ?"
    )

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._state = "idle"
        self._status = "Initialisation..."

        self._tts_ready = False
        self._tts_loading = False
        self._tts_downloading = False
        self._tts_installed = False

        self._tts_error = ""
        self._audio_path = ""

        self._tts_service = TTSService(
            parent=self,
        )

        self._tts_service.statusChanged.connect(
            self._on_tts_status_changed
        )

        self._tts_service.stateChanged.connect(
            self._on_tts_state_changed
        )

        self._tts_service.errorOccurred.connect(
            self._on_tts_error
        )

        self._tts_service.speechStarted.connect(
            self._on_speech_started
        )

        self._tts_service.speechFinished.connect(
            self._on_speech_finished
        )

        self._tts_service.installationStarted.connect(
            self._on_installation_started
        )

        self._tts_service.installationFinished.connect(
            self._on_installation_finished
        )

        self._tts_service.installationFailed.connect(
            self._on_installation_failed
        )

        self._tts_installed = (
            self._tts_service.installed
        )

        if self._tts_installed:
            self._set_status(
                "Chargement du moteur vocal local..."
            )

            self._tts_service.initialize_async()
        else:
            self._set_status(
                "Moteur vocal non installé."
            )

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        return self._status

    @Property(bool, notify=ttsReadyChanged)
    def ttsReady(self) -> bool:
        return self._tts_ready

    @Property(bool, notify=ttsLoadingChanged)
    def ttsLoading(self) -> bool:
        return self._tts_loading

    @Property(bool, notify=ttsDownloadingChanged)
    def ttsDownloading(self) -> bool:
        return self._tts_downloading

    @Property(bool, notify=ttsInstalledChanged)
    def ttsInstalled(self) -> bool:
        return self._tts_installed

    @Property(str, notify=ttsErrorChanged)
    def ttsError(self) -> str:
        return self._tts_error

    @Property(str, notify=audioPathChanged)
    def audioPath(self) -> str:
        return self._audio_path

    @Property(str, notify=stateChanged)
    def assistantState(self) -> str:
        return self._state

    @Slot()
    def downloadTts(self) -> None:
        if self._tts_installed:
            return

        if self._tts_downloading:
            return

        self._clear_error()
        self._tts_service.download()

    @Slot()
    def activate(self) -> None:
        if not self._tts_installed:
            self._set_status(
                "Installez d'abord le moteur vocal."
            )
            return

        if self._tts_downloading:
            return

        if not self._tts_ready:
            if self._tts_loading:
                self._set_status(
                    "Chargement du moteur vocal..."
                )
            else:
                self._set_status(
                    "Le moteur vocal n'est pas disponible."
                )

            return

        if self._tts_service.speaking:
            return

        self._clear_error()

        self._set_state("speaking")

        self._tts_service.speak(
            self.GREETING
        )

    @Slot()
    def speakGreeting(self) -> None:
        self.activate()

    @Slot()
    def audioPlaybackFinished(self) -> None:
        logger.info(
            "[T.A.R.S.][Assistant] "
            "Lecture de la réponse terminée."
        )

        self._tts_service.playback_finished()

        self._set_state("idle")

    def _on_tts_status_changed(
        self,
        status: str,
    ) -> None:
        self._set_status(status)

    def _on_tts_state_changed(
        self,
        state: str,
    ) -> None:
        if state == "loading":
            self._set_tts_loading(True)
            self._set_tts_ready(False)
            self._set_state("loading")

        elif state == "downloading":
            self._set_tts_loading(False)
            self._set_tts_ready(False)
            self._set_tts_downloading(True)
            self._set_state("loading")

        elif state == "ready":
            self._set_tts_loading(False)
            self._set_tts_downloading(False)
            self._set_tts_ready(True)
            self._set_tts_installed(True)

            if self._state in (
                "loading",
                "speaking",
            ):
                self._set_state("idle")

        elif state == "not_installed":
            self._set_tts_loading(False)
            self._set_tts_downloading(False)
            self._set_tts_ready(False)
            self._set_tts_installed(False)

            self._set_state("idle")

        elif state == "speaking":
            self._set_state("speaking")

        elif state == "error":
            self._set_tts_loading(False)
            self._set_tts_downloading(False)
            self._set_tts_ready(False)
            self._set_state("idle")

    def _on_installation_started(self) -> None:
        self._set_tts_downloading(True)
        self._set_tts_loading(False)

        self._set_status(
            "Téléchargement du moteur vocal..."
        )

    def _on_installation_finished(self) -> None:
        self._set_tts_downloading(False)
        self._set_tts_installed(True)
        self._set_tts_ready(True)

        self._set_status(
            "Moteur vocal installé. Utilisable hors ligne."
        )

        self._set_state("idle")

    def _on_installation_failed(self) -> None:
        self._set_tts_downloading(False)
        self._set_tts_ready(False)

        self._set_status(
            "Échec du téléchargement du moteur vocal."
        )

        self._set_state("idle")

    def _on_tts_error(
        self,
        error: str,
    ) -> None:
        logger.error(
            "[T.A.R.S.][TTS] %s",
            error,
        )

        self._set_tts_loading(False)
        self._set_tts_downloading(False)
        self._set_tts_ready(False)

        self._tts_error = error
        self.ttsErrorChanged.emit()

        self._set_state("idle")

    def _on_speech_started(self) -> None:
        self._set_state("speaking")

    def _on_speech_finished(
        self,
        audio_path: str,
    ) -> None:
        self._audio_path = audio_path
        self.audioPathChanged.emit()

        self._set_state("speaking")

        self._set_status(
            "Réponse en cours..."
        )

    def _set_state(
        self,
        value: str,
    ) -> None:
        if value == self._state:
            return

        self._state = value
        self.stateChanged.emit()

    def _set_status(
        self,
        value: str,
    ) -> None:
        if value == self._status:
            return

        self._status = value
        self.statusChanged.emit()

    def _set_tts_ready(
        self,
        value: bool,
    ) -> None:
        if value == self._tts_ready:
            return

        self._tts_ready = value
        self.ttsReadyChanged.emit()

    def _set_tts_loading(
        self,
        value: bool,
    ) -> None:
        if value == self._tts_loading:
            return

        self._tts_loading = value
        self.ttsLoadingChanged.emit()

    def _set_tts_downloading(
        self,
        value: bool,
    ) -> None:
        if value == self._tts_downloading:
            return

        self._tts_downloading = value
        self.ttsDownloadingChanged.emit()

    def _set_tts_installed(
        self,
        value: bool,
    ) -> None:
        if value == self._tts_installed:
            return

        self._tts_installed = value
        self.ttsInstalledChanged.emit()

    def _clear_error(self) -> None:
        if not self._tts_error:
            return

        self._tts_error = ""
        self.ttsErrorChanged.emit()

    def shutdown(self) -> None:
        try:
            self._tts_service.shutdown()
        except Exception:
            logger.exception(
                "[T.A.R.S.] Erreur lors de l'arrêt."
            )
