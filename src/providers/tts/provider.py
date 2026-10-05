"""Contract shared by local TTS providers and their consumers."""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol


class TTSProvider(Protocol):
    @property
    def installed(self) -> bool: ...

    @property
    def initialized(self) -> bool: ...

    @property
    def language(self) -> str: ...

    def set_language(self, language: str) -> None: ...

    def initialize(self, on_status: Callable[[str], None] | None = None) -> None: ...

    def download(self, on_status: Callable[[str], None] | None = None) -> None: ...

    def load(self, language: str, on_status: Callable[[str], None] | None = None) -> None: ...

    def generate(self, text: str, output_path: Path) -> Path: ...

    def generate_stream(self, text: str, stop: threading.Event) -> Iterator[tuple[bytes, int]]:
        """Yield mono float32 PCM bytes and their sample rate."""
        ...

    def shutdown(self) -> None: ...
