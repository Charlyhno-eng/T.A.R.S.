from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from providers.stt.adapter import STTAdapter


logger = logging.getLogger("TARS.STT")


class STTService(QObject):
    """Asynchronous loading and transcription service for Parakeet."""

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    transcriptionReady = Signal(str)
    installationStarted = Signal()
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        language: str = "en",
    ) -> None:
        super().__init__(parent)
        self._adapter = STTAdapter()
        self._language = language
        self._initialized = False
        self._initializing = False
        self._installing = False
        self._transcribing = False
        self._lock = threading.Lock()

    @property
    def installed(self) -> bool:
        return self._adapter.installed

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._initialized

    def set_language(self, language: str) -> None:
        if language not in {"fr", "en"}:
            raise ValueError(f"Unsupported Parakeet language: {language}")
        self._language = language

    def initialize_async(self) -> None:
        if not self.installed:
            self.stateChanged.emit("not_installed")
            return
        with self._lock:
            if self._initialized or self._initializing:
                return
            self._initializing = True
        self.stateChanged.emit("loading")
        threading.Thread(
            target=self._initialize_worker,
            name="TARS-STT-Init",
            daemon=True,
        ).start()

    def _initialize_worker(self) -> None:
        try:
            self._adapter.initialize(on_status=self.statusChanged.emit)
            with self._lock:
                self._initialized = True
                self._initializing = False
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Parakeet est prêt.")
        except Exception as exc:
            logger.exception("Échec du chargement local de Parakeet.")
            with self._lock:
                self._initializing = False
            self.stateChanged.emit("error")
            self.errorOccurred.emit(str(exc))

    def download(self) -> None:
        with self._lock:
            if self._installing:
                return
            self._installing = True
        self.installationStarted.emit()
        self.stateChanged.emit("downloading")
        threading.Thread(
            target=self._download_worker,
            name="TARS-STT-Download",
            daemon=True,
        ).start()

    def _download_worker(self) -> None:
        try:
            self._adapter.download(on_status=self.statusChanged.emit)
            with self._lock:
                self._initialized = True
                self._installing = False
            self.installationFinished.emit()
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Parakeet est installé et disponible hors ligne.")
        except Exception as exc:
            logger.exception("Échec du téléchargement de Parakeet.")
            with self._lock:
                self._installing = False
            self.installationFailed.emit()
            self.errorOccurred.emit(str(exc))
            self.stateChanged.emit("not_installed")

    def transcribe(self, audio_path: Path) -> None:
        with self._lock:
            if not self._initialized or self._transcribing:
                self.errorOccurred.emit("Parakeet n'est pas disponible.")
                return
            self._transcribing = True
        self.stateChanged.emit("transcribing")
        threading.Thread(
            target=self._transcribe_worker,
            args=(audio_path,),
            name="TARS-STT-Transcribe",
            daemon=True,
        ).start()

    def _transcribe_worker(self, audio_path: Path) -> None:
        try:
            self.statusChanged.emit("Transcription de votre message...")
            self.transcriptionReady.emit(
                self._adapter.transcribe(audio_path, language=self._language)
            )
        except Exception as exc:
            logger.exception("Erreur de transcription Parakeet.")
            self.errorOccurred.emit(str(exc))
        finally:
            audio_path.unlink(missing_ok=True)
            with self._lock:
                self._transcribing = False
            if self.initialized:
                self.stateChanged.emit("ready")

    def shutdown(self) -> None:
        self._adapter.shutdown()
        with self._lock:
            self._initialized = False
