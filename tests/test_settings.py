from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from core.settings import Settings


class SettingsTests(unittest.TestCase):
    """Verify persistent application preferences."""

    def make_settings(self, directory: str) -> Settings:
        """Create settings backed by an isolated temporary file."""
        settings = Settings(directory=Path(directory))
        settings._path = Path(directory) / "config.toml"
        return settings

    def test_missing_language_uses_english_default(self) -> None:
        """Use English when no language preference has been saved."""
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(directory)

            self.assertEqual(settings.language(), "en")

    def test_language_is_persisted_and_other_settings_are_preserved(self) -> None:
        """Save the selected language without removing other config sections."""
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(directory)
            settings._path.write_text(
                '[application]\nlanguage = "en"\n\n[other]\nvalue = 42\n',
                encoding="utf-8",
            )

            settings.set_language("fr")

            saved = tomllib.loads(settings._path.read_text(encoding="utf-8"))
            self.assertEqual(settings.language(), "fr")
            self.assertEqual(saved["other"]["value"], 42)

    def test_invalid_language_is_rejected(self) -> None:
        """Reject language codes that the application does not support."""
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(directory)

            with self.assertRaises(ValueError):
                settings.set_language("de")

            self.assertFalse(settings._path.exists())

    def test_invalid_config_language_uses_english_default(self) -> None:
        """Fall back to English when the saved language is unsupported."""
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(directory)
            settings._path.write_text(
                '[application]\nlanguage = "de"\n', encoding="utf-8"
            )

            self.assertEqual(settings.language(), "en")

    def test_shortcut_persists_independently_of_language(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = self.make_settings(directory)
            settings._path.write_text('[other]\nvalue = 42\n', encoding="utf-8")
            self.assertEqual(settings.shortcut(), "")
            settings.set_shortcut("Ctrl+Alt+Space")
            settings.set_language("fr")
            restarted = self.make_settings(directory)
            self.assertEqual(restarted.shortcut(), "Ctrl+Alt+Space")
            self.assertEqual(restarted.language(), "fr")
            restarted.set_shortcut("")
            self.assertEqual(settings.shortcut(), "")
            saved = tomllib.loads(settings._path.read_text(encoding="utf-8"))
            self.assertEqual(saved["other"]["value"], 42)

    def test_malformed_shortcut_preference_is_disabled(self) -> None:
        for content in ('[application]\nshortcut = 42\n', 'application = "bad"\n'):
            with tempfile.TemporaryDirectory() as directory:
                settings = self.make_settings(directory)
                settings._path.write_text(content, encoding="utf-8")
                self.assertEqual(settings.shortcut(), "")
