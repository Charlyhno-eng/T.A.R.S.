from __future__ import annotations

import re
import threading
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot

from providers.llm.adapter import LLMAdapter


class SpeechTextBuffer:
    """Start with a short fragment, then preserve sentence intonation."""

    FIRST_CHUNK_LIMIT = 40
    CLAUSE_LIMIT = 240
    WORD_LIMIT = 400

    def __init__(self) -> None:
        self.pending = ""
        self._started = False

    def add(self, delta: str) -> list[str]:
        self.pending += delta
        chunks = []
        while self.pending:
            # Require whitespace after punctuation to preserve decimals and URLs.
            boundary = re.search(r"[.!?\n][\"'»”)]*\s+", self.pending)
            if boundary:
                end = boundary.end()
            elif not self._started:
                # Never send individual tokens or split a word to TTS. A short
                # opening phrase lets synthesis overlap the rest of the reply.
                clause = re.search(r"[,;:][\"'»”)]*\s+", self.pending)
                if clause:
                    end = clause.end()
                elif len(self.pending) >= self.FIRST_CHUNK_LIMIT:
                    spaces = list(re.finditer(r"\s+", self.pending[:self.FIRST_CHUNK_LIMIT]))
                    if not spaces:
                        break
                    end = spaces[-1].end()
                else:
                    break
            elif len(self.pending) >= self.CLAUSE_LIMIT:
                # A comma/semicolon keeps continuation intonation; arbitrary
                # short fragments make Piper repeatedly sound like it is done.
                clauses = list(re.finditer(r"[,;:][\"'»”)]*\s+",
                                           self.pending[:self.WORD_LIMIT]))
                if clauses:
                    end = clauses[-1].end()
                elif len(self.pending) >= self.WORD_LIMIT:
                    end = self.pending.rfind(" ", 0, self.WORD_LIMIT)
                    if end < 1:
                        break
                else:
                    break
            else:
                break
            chunk, self.pending = self.pending[:end].strip(), self.pending[end:]
            if chunk:
                chunks.append(chunk)
                self._started = True
        return chunks

    def finish(self) -> str:
        chunk, self.pending = self.pending.strip(), ""
        return chunk


class LLMService(QObject):
    """Stream GLM answers asynchronously for the Qt controller."""
    responseUpdated = Signal(str)
    sentenceReady = Signal(str)
    responseReady = Signal(str)
    errorOccurred = Signal(str)
    _event = Signal(int, str, str)

    def __init__(self, parent: QObject | None = None,
                 provider: Any | None = None) -> None:
        super().__init__(parent)
        self._provider = provider if provider is not None else LLMAdapter()
        self._history: list[dict[str, str]] = []
        self._request_id = 0
        self._lock = threading.RLock()
        self._event.connect(self._deliver)

    @Slot(int, str, str)
    def _deliver(self, request_id: int, kind: str, text: str) -> None:
        # Recheck on the Qt thread: cancellation may occur while events are queued.
        with self._lock:
            if request_id != self._request_id:
                return
            signal = {
                "update": self.responseUpdated,
                "sentence": self.sentenceReady,
                "done": self.responseReady,
                "error": self.errorOccurred,
            }[kind]
            signal.emit(text)

    def cancel(self) -> None:
        """Discard signals and history updates from an interrupted request."""
        with self._lock:
            self._request_id += 1

    def reset(self) -> None:
        """Clear the recent conversation and invalidate outstanding requests."""
        with self._lock:
            self.cancel()
            self._history.clear()

    def respond(self, text: str, language: str) -> None:
        """Start an asynchronous GLM request."""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            history = self._history.copy()
        threading.Thread(
            target=self._respond_worker,
            args=(text, language, history, request_id),
            name="TARS-GLM-Response",
            daemon=True,
        ).start()

    def _respond_worker(self, text: str, language: str, history: list[dict[str, str]],
                        request_id: int | None = None) -> None:
        request_id = self._request_id if request_id is None else request_id
        parts: list[str] = []
        buffer = SpeechTextBuffer()
        stream_method = getattr(self._provider, "stream", None)
        chunks = None
        try:
            chunks = (stream_method(text, language, history) if callable(stream_method)
                      else iter([self._provider.complete(text, language, history)]))
            for delta in chunks:
                with self._lock:
                    if request_id != self._request_id:
                        return
                    parts.append(delta)
                    self._event.emit(request_id, "update", "".join(parts).strip())
                    for sentence in buffer.add(delta):
                        self._event.emit(request_id, "sentence", sentence)
            answer = "".join(parts).strip()
            if not answer:
                raise RuntimeError("GLM API returned an empty response.")
            with self._lock:
                if request_id != self._request_id:
                    return
                tail = buffer.finish()
                if tail:
                    self._event.emit(request_id, "sentence", tail)
                self._history = (history + [
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": answer},
                ])[-10:]
                self._event.emit(request_id, "done", answer)
        except (RuntimeError, OSError, ValueError, TypeError) as exc:
            with self._lock:
                if request_id == self._request_id:
                    self._event.emit(request_id, "error", str(exc))
        finally:
            if chunks is not None and callable(getattr(chunks, "close", None)):
                chunks.close()
