from __future__ import annotations

import logging
import threading
from queue import Queue

from PySide6.QtCore import QObject, Signal, Slot

from providers.tts.adapter import TTSAdapter
from core.audio_playback import AudioPlayback


logger = logging.getLogger("TARS.TTS")


class TTSService(QObject):
    """Provide asynchronous offline TTS operations."""

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)

    speechStarted = Signal()
    speechFinished = Signal()
    _audioChunk = Signal(int, bytes, int)
    _generationFinished = Signal(int)
    _generationFailed = Signal(int, str)

    installationStarted = Signal()
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        language: str = "en",
    ) -> None:
        super().__init__(parent)

        self._adapter = TTSAdapter(language=language)

        self._initialized = False
        self._initializing = False
        self._installing = False
        self._speaking = False

        self._lock = threading.Lock()

        self._session = 0
        self._text_queue: Queue[str | None] = Queue()
        self._stop_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._playback = AudioPlayback(self)
        self._playback.started.connect(self._on_playback_started)
        self._playback.finished.connect(self._on_playback_finished)
        self._playback.errorOccurred.connect(self._on_playback_error)
        self._audioChunk.connect(self._on_audio_chunk)
        self._generationFinished.connect(self._on_generation_finished)
        self._generationFailed.connect(self._on_generation_failed)

    @property
    def initialized(self) -> bool:
        """Return whether the provider is ready."""
        with self._lock:
            return self._initialized

    @property
    def installed(self) -> bool:
        """Return whether required local resources are installed."""
        return self._adapter.installed

    def set_language(self, language: str) -> None:
        """Switch voices without keeping the previous model in memory."""
        with self._lock:
            if (self._speaking or self._initializing or self._installing
                    or (self._worker is not None and self._worker.is_alive())):
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

    def begin_response(self) -> None:
        """Start one serialized synthesis worker while GLM is still responding."""
        with self._lock:
            if not self._initialized or self._speaking:
                raise RuntimeError("Le moteur vocal n'est pas disponible.")
            # A cancelled generation must release the model before it is reused.
            if self._worker is not None and self._worker.is_alive():
                raise RuntimeError("Le moteur vocal est occupé.")
            self._session += 1
            session = self._session
            self._speaking = True
            self._text_queue = Queue()
            self._stop_event = threading.Event()
        self._playback.begin()
        self._worker = threading.Thread(
            target=self._speak_worker,
            args=(session, self._text_queue, self._stop_event),
            name="TARS-TTS-Speech",
            daemon=True,
        )
        self._worker.start()

    @Slot(str)
    def speak(self, text: str) -> None:
        """Queue a sentence; synthesis and playback overlap subsequent sentences."""
        if text.strip() and self._speaking:
            self._text_queue.put(text.strip())

    def finish_response(self) -> None:
        """Mark the last sentence without ending playback prematurely."""
        if self._speaking:
            self._text_queue.put(None)

    def _speak_worker(self, session: int, texts: Queue[str | None],
                      stop: threading.Event) -> None:
        try:
            while not stop.is_set():
                text = texts.get()
                if text is None or stop.is_set():
                    break
                for pcm, sample_rate in self._adapter.generate_stream(text, stop):
                    if stop.is_set():
                        return
                    self._audioChunk.emit(session, pcm, sample_rate)
            if not stop.is_set():
                self._generationFinished.emit(session)
        except Exception as exc:
            logger.exception("[T.A.R.S.][TTS] Erreur de génération.")
            if not stop.is_set():
                self._generationFailed.emit(session, str(exc))

    @Slot(int, bytes, int)
    def _on_audio_chunk(self, session: int, pcm: bytes, sample_rate: int) -> None:
        if session == self._session and self._speaking:
            self._playback.append(pcm, sample_rate)

    @Slot(int)
    def _on_generation_finished(self, session: int) -> None:
        if session == self._session and self._speaking:
            self._playback.end()

    @Slot(int, str)
    def _on_generation_failed(self, session: int, message: str) -> None:
        if session == self._session and self._speaking:
            self._on_playback_error(message)

    def _on_playback_started(self) -> None:
        self.statusChanged.emit("Réponse de T.A.R.S....")
        self.stateChanged.emit("speaking")
        self.speechStarted.emit()

    def _on_playback_finished(self) -> None:
        with self._lock:
            self._speaking = False
        self.stateChanged.emit("ready")
        self.speechFinished.emit()

    def _on_playback_error(self, message: str) -> None:
        self.cancel_response()
        self.errorOccurred.emit(message)
        if self.initialized:
            self.stateChanged.emit("ready")

    def cancel_response(self) -> None:
        """Stop audio and invalidate queued worker signals after an error."""
        with self._lock:
            self._session += 1
            self._speaking = False
            self._stop_event.set()
            self._text_queue.put(None)
        self._playback.stop()

    def shutdown(self) -> None:
        """Stop synthesis before releasing provider resources."""
        self.cancel_response()
        if self._worker is not None:
            self._worker.join(timeout=5)
            if self._worker.is_alive():
                logger.warning("Pocket TTS is still stopping; leaving resources to its worker.")
                return
        try:
            self._adapter.shutdown()
        except Exception:
            logger.exception("[T.A.R.S.][TTS] Erreur lors de l'arrêt.")
        with self._lock:
            self._initialized = False
        self.stateChanged.emit("idle")
