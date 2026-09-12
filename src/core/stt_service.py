from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from providers.stt.adapter import STTAdapter


logger = logging.getLogger("TARS.STT")


class STTService(QObject):
    """Chargement et transcription asynchrones de Parakeet."""

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    transcriptionReady = Signal(str)
    installationStarted = Signal()
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._adapter = STTAdapter()
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
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Parakeet est prêt.")
        except Exception as exc:
            logger.exception("Échec du chargement local de Parakeet.")
            self.stateChanged.emit("error")
            self.errorOccurred.emit(str(exc))
        finally:
            with self._lock:
                self._initializing = False

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
            self.installationFinished.emit()
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Parakeet est installé et disponible hors ligne.")
        except Exception as exc:
            logger.exception("Échec du téléchargement de Parakeet.")
            self.installationFailed.emit()
            self.errorOccurred.emit(str(exc))
            self.stateChanged.emit("not_installed")
        finally:
            with self._lock:
                self._installing = False

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
            self.transcriptionReady.emit(self._adapter.transcribe(audio_path))
        except Exception as exc:
            logger.exception("Erreur de transcription Parakeet.")
            self.errorOccurred.emit(str(exc))
        finally:
            with self._lock:
                self._transcribing = False
            if self.initialized:
                self.stateChanged.emit("ready")

    def shutdown(self) -> None:
        self._adapter.shutdown()
        with self._lock:
            self._initialized = False
