from __future__ import annotations

import threading
from collections.abc import Callable


class ModelStandby:
    """Keep conversation models warm, then request serialized idle cleanup."""

    VISIBLE_IDLE_SECONDS = 120.0
    BACKGROUND_IDLE_SECONDS = 30.0

    def __init__(self, expire: Callable[[int], None]) -> None:
        self._expire = expire
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._revision = 0
        self._busy = 0
        self._active = False
        self._background = False
        self._closed = False

    def _reschedule(self) -> None:
        # Caller owns _lock. Revisions also invalidate cleanup already queued
        # behind inference in the service's provider lock.
        self._revision += 1
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self._closed or self._busy or self._active:
            return
        delay = (self.BACKGROUND_IDLE_SECONDS if self._background
                 else self.VISIBLE_IDLE_SECONDS)
        self._timer = threading.Timer(delay, self._expire, (self._revision,))
        self._timer.daemon = True
        self._timer.start()

    def hold(self) -> None:
        with self._lock:
            self._busy += 1
            self._reschedule()

    def release(self) -> None:
        with self._lock:
            self._busy -= 1
            self._reschedule()

    def set_active(self, active: bool) -> None:
        with self._lock:
            if self._active != active:
                self._active = active
                self._reschedule()

    def set_background(self, background: bool) -> None:
        with self._lock:
            if self._background != background:
                self._background = background
                self._reschedule()

    def is_current(self, revision: int) -> bool:
        with self._lock:
            return (not self._closed and not self._busy and not self._active
                    and revision == self._revision)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._reschedule()
