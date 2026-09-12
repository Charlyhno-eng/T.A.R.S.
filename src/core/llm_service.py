from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading

from PySide6.QtCore import QObject, Signal

from agents.registry import AgentRegistry
from core.intent_matcher import IntentMatcher
from core.response_router import ResponseRouter
from core.responses import ResponseCatalog
from providers.llm.adapter import LLMAdapter


logger = logging.getLogger("TARS.LLM")


class LLMService(QObject):
    """Provide asynchronous local Needle 2 operations."""

    statusChanged = Signal(str)
    stateChanged = Signal(str)
    errorOccurred = Signal(str)
    responseReady = Signal(str)
    installationFinished = Signal()
    installationFailed = Signal()

    def __init__(self, parent: QObject | None = None, language: str = "fr") -> None:
        super().__init__(parent)
        self._agents = AgentRegistry()
        self._response_catalog = ResponseCatalog()
        self._intent_matcher = IntentMatcher(self._response_catalog)
        self._responses = ResponseRouter(self._response_catalog, self._agents)
        self._adapter = LLMAdapter(
            agent_definitions=self._agents.tool_definitions,
        )
        self._language = language
        self._initialized = False
        self._initializing = False
        self._installing = False
        self._responding = False
        self._lock = threading.Lock()
        self._worker = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="TARS-LLM",
        )

    @property
    def installed(self) -> bool:
        return self._adapter.installed

    @property
    def initialized(self) -> bool:
        with self._lock:
            return self._initialized

    def set_language(self, language: str) -> None:
        if language not in {"fr", "en"}:
            raise ValueError(f"Unsupported Needle 2 language: {language}")
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
        self._worker.submit(self._initialize_worker)

    def _initialize_worker(self) -> None:
        try:
            self._adapter.initialize(on_status=self.statusChanged.emit)
            with self._lock:
                self._initialized = True
                self._initializing = False
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Needle 2 est prêt.")
        except Exception as exc:
            logger.exception("Échec du chargement local de Needle 2.")
            with self._lock:
                self._initializing = False
            self.stateChanged.emit("error")
            self.errorOccurred.emit(str(exc))

    def download(self) -> None:
        with self._lock:
            if self._installing:
                return
            self._installing = True
        self.stateChanged.emit("downloading")
        self._worker.submit(self._download_worker)

    def _download_worker(self) -> None:
        try:
            self._adapter.download(on_status=self.statusChanged.emit)
            with self._lock:
                self._initialized = True
                self._installing = False
            self.installationFinished.emit()
            self.stateChanged.emit("ready")
            self.statusChanged.emit("Needle 2 est installé et disponible hors ligne.")
        except Exception as exc:
            logger.exception("Échec du téléchargement de Needle 2.")
            with self._lock:
                self._installing = False
            self.installationFailed.emit()
            self.errorOccurred.emit(str(exc))
            self.stateChanged.emit("not_installed")

    def respond(self, text: str) -> None:
        with self._lock:
            if not self._initialized or self._responding:
                self.errorOccurred.emit("Needle 2 n'est pas disponible.")
                return
            self._responding = True
        self.stateChanged.emit("thinking")
        self._worker.submit(self._respond_worker, text)

    def _respond_worker(self, text: str) -> None:
        try:
            self.statusChanged.emit("Analyse locale de votre demande...")
            route = self._intent_matcher.match(text)
            if route is None:
                route = self._adapter.select_route(text)
            self.responseReady.emit(
                self._responses.respond(route, text, self._language)
            )
        except Exception as exc:
            logger.exception("Erreur Needle 2.")
            self.errorOccurred.emit(str(exc))
        finally:
            with self._lock:
                self._responding = False
            if self.initialized:
                self.stateChanged.emit("ready")

    def shutdown(self) -> None:
        future = self._worker.submit(self._adapter.shutdown)
        future.result()
        self._worker.shutdown(wait=True)
        with self._lock:
            self._initialized = False
