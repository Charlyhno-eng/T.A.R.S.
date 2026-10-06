from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
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
        self._workers: set[threading.Thread] = set()
        self._shutdown_requested = False
        self._resources_released = False

    def _start_worker(self, target: Callable, name: str, args: tuple = ()) -> None:
        with self._lock:
            if self._shutdown_requested:
                return
            worker = threading.Thread(target=self._run_worker, args=(target, args),
                                      name=name, daemon=True)
            self._workers.add(worker)
            worker.start()

    def _run_worker(self, target: Callable, args: tuple) -> None:
        try:
            target(*args)
        finally:
            with self._lock:
                self._workers.discard(threading.current_thread())
            self._release_resources_if_stopped()

    def _release_resources_if_stopped(self) -> None:
        with self._lock:
            if (not self._shutdown_requested or self._workers
                    or self._resources_released):
                return
            self._resources_released = True
            self._initialized = False
        self._adapter.shutdown()

    @property
    def installed(self) -> bool:
        """Return whether required local resources are installed."""
        return self._adapter.installed

    @property
    def initialized(self) -> bool:
        """Return whether the provider is ready."""
        with self._lock:
            return self._initialized

    def set_language(self, language: str) -> None:
        """Set the language used by the provider."""
        if language not in {"fr", "en"}:
            raise ValueError(f"Unsupported Parakeet language: {language}")
        self._language = language

    def initialize_async(self) -> None:
        """Load the installed speech recognizer in a background thread."""
        if not self.installed:
            self.stateChanged.emit("not_installed")
            return
        with self._lock:
            if self._initialized or self._initializing:
                return
            self._initializing = True
        self.stateChanged.emit("loading")
        self._start_worker(self._initialize_worker, "TARS-STT-Init")

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
        """Download and prepare the provider resources."""
        with self._lock:
            if self._installing:
                return
            self._installing = True
        self.installationStarted.emit()
        self.stateChanged.emit("downloading")
        self._start_worker(self._download_worker, "TARS-STT-Download")

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
        """Convert an audio file into text."""
        with self._lock:
            if not self._initialized or self._transcribing:
                self.errorOccurred.emit("Parakeet n'est pas disponible.")
                return
            self._transcribing = True
        self.stateChanged.emit("transcribing")
        self._start_worker(self._transcribe_worker, "TARS-STT-Transcribe", (audio_path,))

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
        """Release file-backed weights only after their last worker stops."""
        with self._lock:
            self._shutdown_requested = True
            workers = tuple(self._workers)
        deadline = time.monotonic() + 5
        for worker in workers:
            worker.join(timeout=max(0, deadline - time.monotonic()))
        # A slow load/inference releases its own resources in _run_worker.
        self._release_resources_if_stopped()
