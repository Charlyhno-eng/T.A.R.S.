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

    Cette classe constitue la frontière entre QML et la logique métier.

    QML ne connaît :
    - ni Pocket TTS ;
    - ni le provider ;
    - ni l'adapter ;
    - ni la génération audio.

    QML communique uniquement avec ce contrôleur.
    """

    stateChanged = Signal()
    statusChanged = Signal()
    ttsReadyChanged = Signal()
    ttsLoadingChanged = Signal()
    ttsErrorChanged = Signal()
    audioPathChanged = Signal()

    GREETING = (
        "Ici votre assistant TARS, comment puis-je vous aider aujourd'hui ?"
    )

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._state = "idle"
        self._status = "Initialisation..."
        self._tts_ready = False
        self._tts_loading = False
        self._tts_error = ""
        self._audio_path = ""

        self._tts_service = TTSService(
            parent=self,
        )

        # --------------------------------------------------------------
        # Connexions avec le service TTS
        # --------------------------------------------------------------

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

        # Le chargement du modèle démarre immédiatement, mais dans
        # un thread séparé afin de ne jamais bloquer l'interface.
        self._tts_service.initialize_async()

    # ==================================================================
    # Propriétés exposées à QML
    # ==================================================================

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        """
        État actuel de T.A.R.S.

        Valeurs possibles :
        - idle
        - loading
        - speaking
        - error
        """
        return self._state

    @Property(str, notify=statusChanged)
    def status(self) -> str:
        """
        Message d'information destiné à l'interface.
        """
        return self._status

    @Property(bool, notify=ttsReadyChanged)
    def ttsReady(self) -> bool:
        """
        Indique si le moteur TTS est prêt.
        """
        return self._tts_ready

    @Property(bool, notify=ttsLoadingChanged)
    def ttsLoading(self) -> bool:
        """
        Indique si le moteur TTS est actuellement en cours
        d'initialisation.
        """
        return self._tts_loading

    @Property(str, notify=ttsErrorChanged)
    def ttsError(self) -> str:
        """
        Dernière erreur TTS.
        """
        return self._tts_error

    @Property(str, notify=audioPathChanged)
    def audioPath(self) -> str:
        """
        Chemin du dernier fichier audio généré.
        """
        return self._audio_path

    # ------------------------------------------------------------------
    # Compatibilité avec les composants QML existants
    # ------------------------------------------------------------------

    @Property(str, notify=stateChanged)
    def assistantState(self) -> str:
        """
        Alias permettant aux composants QML existants d'utiliser
        assistant.assistantState.
        """
        return self._state

    # ==================================================================
    # Actions QML
    # ==================================================================

    @Slot()
    def activate(self) -> None:
        """
        Action principale de T.A.R.S.

        Appelée lorsque l'utilisateur clique sur la sphère.
        """

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
        """
        Alias explicite pour demander la phrase d'accueil.
        """
        self.activate()

    @Slot()
    def audioPlaybackFinished(self) -> None:
        """
        Appelée par QML lorsque MediaPlayer arrive exactement à la
        fin naturelle du fichier audio.

        C'est le SEUL endroit où une prise de parole normale repasse
        explicitement en veille.
        """

        logger.info(
            "[T.A.R.S.][Assistant] Lecture de la réponse terminée."
        )

        self._tts_service.playback_finished()

        self._set_state("idle")

    # ==================================================================
    # Callbacks TTS
    # ==================================================================

    def _on_tts_status_changed(self, status: str) -> None:
        self._set_status(status)

    def _on_tts_state_changed(self, state: str) -> None:
        if state == "loading":
            self._set_tts_loading(True)
            self._set_tts_ready(False)

            self._set_state("loading")

        elif state == "ready":
            self._set_tts_loading(False)
            self._set_tts_ready(True)

            # ----------------------------------------------------------
            # IMPORTANT
            # ----------------------------------------------------------
            #
            # "ready" peut maintenant être émis après la vraie fin de
            # lecture audio.
            #
            # On repasse donc en idle si T.A.R.S. était en train de
            # parler.
            #
            # Lors de l'initialisation, _state vaut "loading", ce qui
            # permet également de revenir normalement à idle.
            # ----------------------------------------------------------

            if self._state in ("loading", "speaking"):
                self._set_state("idle")

        elif state == "speaking":
            self._set_state("speaking")

        elif state == "error":
            self._set_tts_loading(False)
            self._set_tts_ready(False)
            self._set_state("idle")

    def _on_tts_error(self, error: str) -> None:
        logger.error(
            "[T.A.R.S.][TTS] %s",
            error,
        )

        self._set_tts_loading(False)
        self._set_tts_ready(False)
        self._set_state("idle")

        self._tts_error = error
        self.ttsErrorChanged.emit()

    def _on_speech_started(self) -> None:
        self._set_state("speaking")

    def _on_speech_finished(self, audio_path: str) -> None:
        """
        Appelé lorsque le fichier WAV est prêt.

        ATTENTION :

        Cela ne signifie PAS que T.A.R.S. a terminé de parler.

        Le fichier va seulement être transmis à MediaPlayer.
        L'état reste donc "speaking".
        """

        self._audio_path = audio_path
        self.audioPathChanged.emit()

        self._set_state("speaking")

        self._set_status(
            "Réponse en cours..."
        )

    # ==================================================================
    # Helpers
    # ==================================================================

    def _set_state(self, value: str) -> None:
        if value == self._state:
            return

        self._state = value

        self.stateChanged.emit()

    def _set_status(self, value: str) -> None:
        if value == self._status:
            return

        self._status = value

        self.statusChanged.emit()

    def _set_tts_ready(self, value: bool) -> None:
        if value == self._tts_ready:
            return

        self._tts_ready = value

        self.ttsReadyChanged.emit()

    def _set_tts_loading(self, value: bool) -> None:
        if value == self._tts_loading:
            return

        self._tts_loading = value

        self.ttsLoadingChanged.emit()

    def _clear_error(self) -> None:
        if not self._tts_error:
            return

        self._tts_error = ""
        self.ttsErrorChanged.emit()

    # ==================================================================
    # Arrêt
    # ==================================================================

    def shutdown(self) -> None:
        """
        Arrêt propre du service TTS.
        """

        try:
            self._tts_service.shutdown()

        except Exception:
            logger.exception(
                "[T.A.R.S.] Erreur lors de l'arrêt."
            )
