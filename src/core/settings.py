from __future__ import annotations

from pathlib import Path
import json
import re
import tomllib
import os


class Settings:
    """Lightweight persistent preferences for T.A.R.S."""

    DEFAULT_LANGUAGE = "en"
    SUPPORTED_LANGUAGES = {"fr", "en"}

    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parents[2] / "config" / "config.toml"
        self._key_path = self._path.parent / "llm_api_key"

    def llm_api_key(self) -> str:
        """Read the user-provided API key, if one was saved."""
        try:
            return self._key_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""

    def set_llm_api_key(self, key: str) -> None:
        """Save or remove the API key in a user-only file."""
        key = key.strip()
        if not key:
            self._key_path.unlink(missing_ok=True)
            return
        self._key_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._key_path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as key_file:
                key_file.write(key)
            temporary.replace(self._key_path)
        finally:
            temporary.unlink(missing_ok=True)

    def language(self) -> str:
        """Return the selected language."""
        data = self._read()
        application = data.get("application", {})
        if not isinstance(application, dict):
            return self.DEFAULT_LANGUAGE
        language = application.get("language", self.DEFAULT_LANGUAGE)
        if language in self.SUPPORTED_LANGUAGES:
            return language
        return self.DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        """Persist the selected application and voice language."""
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Langue non prise en charge : {language}")
        self._set_application_value("language", language)

    def shortcut(self) -> str:
        """Return the saved global shortcut; an empty value disables it."""
        application = self._read().get("application", {})
        value = application.get("shortcut", "") if isinstance(application, dict) else ""
        return value if isinstance(value, str) else ""

    def set_shortcut(self, shortcut: str) -> None:
        self._set_application_value("shortcut", shortcut)

    def _set_application_value(self, name: str, value: str) -> None:
        """Update one preference while preserving the other TOML sections."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        content = self._path.read_text(encoding="utf-8") if self._path.exists() else ""
        section = re.compile(r"(?ms)^\[application\]\s*$.*?(?=^\[|\Z)")
        match = section.search(content)
        setting = f"{name} = {json.dumps(value, ensure_ascii=False)}"
        if match:
            application = match.group(0)
            pattern = rf"(?m)^{re.escape(name)}\s*=.*$"
            if re.search(pattern, application):
                application = re.sub(
                    pattern,
                    lambda _: setting,
                    application,
                    count=1,
                )
            else:
                application = application.rstrip() + f"\n{setting}\n\n"
            content = content[:match.start()] + application + content[match.end():]
        else:
            separator = "" if not content or content.endswith("\n\n") else "\n"
            content += f"{separator}[application]\n{setting}\n"
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(self._path)

    def _read(self) -> dict[str, object]:
        try:
            with self._path.open("rb") as config_file:
                data = tomllib.load(config_file)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
