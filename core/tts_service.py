from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot

from providers.tts.adapter import TTSAdapter


logger = logging.getLogger("TARS.TTS")


class TTSService(QObject):
    """
    Service métier TTS de T.A.R.S.

    Responsabilités :

    - initialiser le moteur vocal en arrière-plan ;
    - transmettre les informations de chargement ;
    - générer les fichiers audio ;
    - gérer l'état de génération ;
    - ne jamais bloquer le thread Qt principal.

    Ce service ne connaît pas l'implémentation réelle du moteur vocal.
    Il communique uniquement avec TTSAdapter.
    """

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    speechStarted = Signal()
    speechFinished = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._adapter = TTSAdapter()

        self._initialized = False
        self._initializing = False
        self._speaking = False

        self._lock = threading.Lock()

        self._audio_directory = (
            Path("/tmp") / "tars_tts"
        )

        self._audio_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ==================================================================
    # État
    # ==================================================================

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._initialized

    @property
    def initializing(self) -> bool:
        with self._lock:
            return self._initializing

    @property
    def speaking(self) -> bool:
        with self._lock:
            return self._speaking

    # ==================================================================
    # Initialisation
    # ==================================================================

    def initialize_async(self) -> None:
        """
        Initialise le moteur vocal dans un thread Python séparé.
        """

        with self._lock:
            if self._initialized or self._initializing:
                return

            self._initializing = True

        self.stateChanged.emit("loading")

        self.statusChanged.emit(
            "Préparation du moteur vocal..."
        )

        thread = threading.Thread(
            target=self._initialize_worker,
            name="TARS-TTS-Init",
            daemon=True,
        )

        thread.start()

    def _initialize_worker(self) -> None:
        try:
            logger.info(
                "[T.A.R.S.][TTS] Initialisation du moteur..."
            )

            self._adapter.initialize(
                on_status=self._on_provider_status,
            )

            with self._lock:
                self._initialized = True

            self.stateChanged.emit("ready")

            self.statusChanged.emit(
                "Moteur vocal prêt."
            )

            logger.info(
                "[T.A.R.S.][TTS] Moteur vocal prêt."
            )

        except Exception as exc:
            logger.exception(
                "[T.A.R.S.][TTS] Échec du chargement"
            )

            with self._lock:
                self._initialized = False

            message = str(exc)

            self.stateChanged.emit("error")

            self.errorOccurred.emit(
                message
            )

            self.statusChanged.emit(
                "Impossible de charger le moteur vocal."
            )

        finally:
            with self._lock:
                self._initializing = False

    # ==================================================================
    # Statut provider
    # ==================================================================

    def _on_provider_status(
        self,
        message: str,
    ) -> None:
        logger.info(
            "[T.A.R.S.][TTS] %s",
            message,
        )

        self.statusChanged.emit(message)

    # ==================================================================
    # Génération vocale
    # ==================================================================

    @Slot(str)
    def speak(
        self,
        text: str,
    ) -> None:
        """
        Génère l'audio correspondant au texte.

        La génération est réalisée dans un thread séparé.
        """

        text = text.strip()

        if not text:
            return

        with self._lock:
            if not self._initialized:
                should_reject = True
            elif self._speaking:
                should_reject = True
            else:
                should_reject = False
                self._speaking = True

        if should_reject:
            self.statusChanged.emit(
                "Le moteur vocal est encore en préparation."
            )

            return

        self.stateChanged.emit("speaking")
        self.speechStarted.emit()

        thread = threading.Thread(
            target=self._speak_worker,
            args=(text,),
            name="TARS-TTS-Speech",
            daemon=True,
        )

        thread.start()

    def _speak_worker(
        self,
        text: str,
    ) -> None:
        audio_path = (
            self._audio_directory
            / f"tars_{uuid.uuid4().hex}.wav"
        )

        try:
            logger.info(
                "[T.A.R.S.][TTS] Génération : %s",
                text,
            )

            self.statusChanged.emit(
                "Génération de la réponse vocale..."
            )

            generated_path = self._adapter.generate(
                text=text,
                output_path=audio_path,
            )

            logger.info(
                "[T.A.R.S.][TTS] Audio généré : %s",
                generated_path,
            )

            self.speechFinished.emit(
                str(generated_path)
            )

        except Exception as exc:
            logger.exception(
                "[T.A.R.S.][TTS] Erreur de génération"
            )

            self.errorOccurred.emit(
                str(exc)
            )

            self.statusChanged.emit(
                "Erreur lors de la génération audio."
            )

        finally:
            with self._lock:
                self._speaking = False

            if self.initialized:
                self.stateChanged.emit("ready")

    # ==================================================================
    # Arrêt
    # ==================================================================

    def shutdown(self) -> None:
        """
        Arrête proprement le provider TTS.
        """

        try:
            self._adapter.shutdown()

        except Exception:
            logger.exception(
                "[T.A.R.S.][TTS] Erreur lors de l'arrêt"
            )

        with self._lock:
            self._initialized = False
            self._speaking = False

        self.stateChanged.emit("idle")
