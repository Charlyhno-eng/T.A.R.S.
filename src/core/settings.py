from __future__ import annotations

import json
from pathlib import Path


class Settings:
    """Lightweight persistent preferences for T.A.R.S."""

    DEFAULT_LANGUAGE = "fr"
    SUPPORTED_LANGUAGES = {"fr", "en"}

    def __init__(self) -> None:
        self._path = Path.home() / ".tars" / "settings.json"

    def language(self) -> str:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            language = data.get("language", self.DEFAULT_LANGUAGE)
            if language in self.SUPPORTED_LANGUAGES:
                return language
        except (OSError, ValueError, TypeError):
            pass
        return self.DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Langue non prise en charge : {language}")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"language": language}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self._path)
