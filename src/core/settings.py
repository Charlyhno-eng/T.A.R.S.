from __future__ import annotations

from pathlib import Path
import re
import tomllib


class Settings:
    """Lightweight persistent preferences for T.A.R.S."""

    DEFAULT_LANGUAGE = "en"
    SUPPORTED_LANGUAGES = {"fr", "en"}

    def __init__(self) -> None:
        self._path = Path(__file__).resolve().parents[2] / "config" / "config.toml"

    def language(self) -> str:
        data = self._read()
        application = data.get("application", {})
        if not isinstance(application, dict):
            return self.DEFAULT_LANGUAGE
        language = application.get("language", self.DEFAULT_LANGUAGE)
        if language in self.SUPPORTED_LANGUAGES:
            return language
        return self.DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Langue non prise en charge : {language}")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        content = self._path.read_text(encoding="utf-8") if self._path.exists() else ""
        section = re.compile(r"(?ms)^\[application\]\s*$.*?(?=^\[|\Z)")
        match = section.search(content)
        if match:
            application = match.group(0)
            if re.search(r"(?m)^language\s*=.*$", application):
                application = re.sub(
                    r'(?m)^language\s*=.*$',
                    f'language = "{language}"',
                    application,
                    count=1,
                )
            else:
                application = application.rstrip() + f'\nlanguage = "{language}"\n'
            content = content[:match.start()] + application + content[match.end():]
        else:
            separator = "" if not content or content.endswith("\n\n") else "\n"
            content += f'{separator}[application]\nlanguage = "{language}"\n'
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(self._path)

    def _read(self) -> dict[str, object]:
        try:
            with self._path.open("rb") as config_file:
                data = tomllib.load(config_file)
        except (OSError, tomllib.TOMLDecodeError):
            return {}
        return data if isinstance(data, dict) else {}
