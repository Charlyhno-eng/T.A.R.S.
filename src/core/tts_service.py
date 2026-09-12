from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from providers.tts.adapter import TTSAdapter


logger = logging.getLogger("TARS.TTS")


class TTSService(QObject):
    """Provide asynchronous offline TTS operations."""

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)

    speechStarted = Signal()
    speechFinished = Signal(str)

    installationStarted = Signal()
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        language: str = "fr",
    ) -> None:
        super().__init__(parent)

        self._adapter = TTSAdapter(language=language)

        self._initialized = False
        self._initializing = False
        self._installing = False
        self._speaking = False

        self._lock = threading.Lock()

        self._audio_directory = (
            Path("/tmp") / "tars_tts"
        )

        self._audio_directory.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._audio_path: Path | None = None

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._initialized

    @property
    def initializing(self) -> bool:
        with self._lock:
            return self._initializing

    @property
    def installing(self) -> bool:
        with self._lock:
            return self._installing

    @property
    def speaking(self) -> bool:
        with self._lock:
            return self._speaking

    @property
    def installed(self) -> bool:
        return self._adapter.installed

    @property
    def language(self) -> str:
        return self._adapter.language

    def set_language(self, language: str) -> None:
        """Switch voices without keeping the previous model in memory."""
        with self._lock:
            if self._speaking or self._initializing or self._installing:
                raise RuntimeError("Le moteur vocal est occupé.")
            if language == self._adapter.language:
                return
            self._initialized = False
        self._adapter.set_language(language)
        self.stateChanged.emit("not_installed")

    def initialize_async(self) -> None:
        """Load the previously installed engine without downloading."""

        if not self.installed:
            self.statusChanged.emit(
                "Moteur vocal non installé."
            )
            self.stateChanged.emit("not_installed")
            return

        with self._lock:
            if self._initialized or self._initializing:
                return

            self._initializing = True

        self.stateChanged.emit("loading")
        self.statusChanged.emit(
            "Chargement du moteur vocal local..."
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
                "[T.A.R.S.][TTS] Initialisation locale..."
            )

            self._adapter.initialize(
                on_status=self._on_provider_status,
            )

            with self._lock:
                self._initialized = True
                self._initializing = False

            self.stateChanged.emit("ready")
            self.statusChanged.emit(
                "Moteur vocal prêt."
            )

            logger.info(
                "[T.A.R.S.][TTS] Moteur vocal local prêt."
            )

        except Exception as exc:
            logger.exception(
                "[T.A.R.S.][TTS] Échec du chargement local."
            )

            with self._lock:
                self._initialized = False
                self._initializing = False

            self.stateChanged.emit("error")
            self.errorOccurred.emit(str(exc))
            self.statusChanged.emit(
                "Impossible de charger le moteur vocal local."
            )

    @Slot()
    def download(self) -> None:
        """Install the voice engine using an explicit user action."""

        with self._lock:
            if self._installing:
                return

            if self._speaking:
                return

            self._installing = True

        self.installationStarted.emit()

        self.stateChanged.emit("downloading")
        self.statusChanged.emit(
            "Téléchargement du moteur vocal..."
        )

        thread = threading.Thread(
            target=self._download_worker,
            name="TARS-TTS-Download",
            daemon=True,
        )

        thread.start()

    def _download_worker(self) -> None:
        try:
            logger.info(
                "[T.A.R.S.][TTS] Début du téléchargement."
            )

            self._adapter.download(
                on_status=self._on_provider_status,
            )

            with self._lock:
                self._initialized = True
                self._installing = False

            logger.info(
                "[T.A.R.S.][TTS] Téléchargement terminé."
            )

            self.installationFinished.emit()

            self.stateChanged.emit("ready")
            self.statusChanged.emit(
                "Moteur vocal installé. T.A.R.S. fonctionne hors ligne."
            )

        except Exception as exc:
            logger.exception(
                "[T.A.R.S.][TTS] Échec du téléchargement."
            )

            with self._lock:
                self._initialized = False
                self._installing = False

            self.installationFailed.emit()
            self.errorOccurred.emit(str(exc))

            self.stateChanged.emit("not_installed")
            self.statusChanged.emit(
                "Échec du téléchargement du moteur vocal."
            )

    def _on_provider_status(
        self,
        message: str,
    ) -> None:
        logger.info(
            "[T.A.R.S.][TTS] %s",
            message,
        )

        self.statusChanged.emit(message)

    @Slot(str)
    def speak(
        self,
        text: str,
    ) -> None:
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
                "Le moteur vocal n'est pas disponible."
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
        audio_path = self._audio_directory / f"tars_{uuid.uuid4().hex}.wav"

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

            with self._lock:
                self._audio_path = generated_path

            logger.info(
                "[T.A.R.S.][TTS] Audio généré : %s",
                generated_path,
            )

            self.speechFinished.emit(
                str(generated_path)
            )

        except Exception as exc:
            logger.exception(
                "[T.A.R.S.][TTS] Erreur de génération."
            )

            with self._lock:
                self._speaking = False

            audio_path.unlink(missing_ok=True)

            self.errorOccurred.emit(str(exc))
            self.statusChanged.emit(
                "Erreur lors de la génération audio."
            )

            if self.initialized:
                self.stateChanged.emit("ready")

    @Slot()
    def playback_finished(self) -> None:
        """Release the speaking state after media playback ends."""

        with self._lock:
            if not self._speaking:
                return

            self._speaking = False
            audio_path = self._audio_path
            self._audio_path = None

        logger.info(
            "[T.A.R.S.][TTS] Lecture audio terminée."
        )

        self.statusChanged.emit(
            "Moteur vocal prêt."
        )

        self.stateChanged.emit("ready")
        if audio_path is not None:
            audio_path.unlink(missing_ok=True)

    def shutdown(self) -> None:
        try:
            self._adapter.shutdown()
        except Exception:
            logger.exception(
                "[T.A.R.S.][TTS] Erreur lors de l'arrêt."
            )

        with self._lock:
            self._initialized = False
            self._speaking = False
            audio_path = self._audio_path
            self._audio_path = None

        if audio_path is not None:
            audio_path.unlink(missing_ok=True)
        self.stateChanged.emit("idle")
