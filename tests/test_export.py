from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QApplication

from core.exporter import copy_bundle, host_platform, new_export_directory
from core.native_shortcut import NativeShortcut, WindowsEventFilter
from core.paths import resource_directory, temporary_directory
from core.settings import Settings
from core.export_service import ExportService


class ExportTests(unittest.TestCase):
    def test_platform_targets_are_explicit(self) -> None:
        for system, target in (("linux", "linux"), ("win32", "windows"), ("darwin", "macos")):
            with patch("core.exporter.sys.platform", system):
                self.assertEqual(host_platform(), target)

    def test_frozen_resources_do_not_depend_on_working_directory(self) -> None:
        with patch("core.paths.sys._MEIPASS", "/bundle/resources", create=True):
            self.assertEqual(resource_directory(), Path("/bundle/resources"))
        with patch("core.paths.tempfile.gettempdir", return_value="/system/temp"):
            self.assertEqual(temporary_directory("tars_stt"), Path("/system/temp/tars_stt"))

    def test_legacy_settings_migrate_once_and_removed_key_stays_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "checkout" / "config"
            legacy.mkdir(parents=True)
            (legacy / "config.toml").write_text('[application]\nlanguage = "fr"\nshortcut = "Ctrl+Tab"\n')
            (legacy / "llm_api_key").write_text("old-test-key")
            with patch("core.settings.resource_directory", return_value=legacy.parent), patch(
                "core.settings.data_directory", return_value=root / "user"
            ):
                settings = Settings()
                self.assertEqual(settings.language(), "fr")
                self.assertEqual(settings.shortcut(), "Ctrl+Tab")
                self.assertEqual(settings.llm_api_key(), "old-test-key")
                if os.name == "posix":
                    self.assertEqual(settings._key_path.stat().st_mode & 0o077, 0)
                settings.set_llm_api_key("")
                settings.set_language("en")
                restarted = Settings()
                self.assertEqual(restarted.llm_api_key(), "")
                self.assertEqual(restarted.language(), "en")
                self.assertEqual(restarted.shortcut(), "Ctrl+Tab")

    def test_exported_settings_stay_writable_outside_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("core.settings.data_directory", return_value=Path(directory)), patch(
                "core.settings.resource_directory", return_value=Path(directory) / "bundle"
            ):
                settings = Settings()
                settings.set_shortcut("Ctrl+Alt+Space")
                self.assertEqual(Settings().shortcut(), "Ctrl+Alt+Space")
                self.assertFalse((Path(directory) / "bundle").exists())

    def test_exports_do_not_overwrite_prior_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = new_export_directory(Path(directory), "linux")
            second = new_export_directory(Path(directory), "linux")
            self.assertNotEqual(first, second)
            self.assertTrue(first.exists() and second.exists())

    def test_packaged_copy_includes_dependencies_and_rejects_recursive_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "TARS"
            source.mkdir()
            (source / "TARS.exe").write_bytes(b"executable")
            dependencies = source / "_internal"
            dependencies.mkdir()
            (dependencies / "library.dll").write_bytes(b"dependency")
            with patch("core.exporter.sys.executable", str(source / "TARS.exe")), patch(
                "core.exporter.sys.platform", "win32"
            ):
                output = copy_bundle(Path(directory) / "exports")
                self.assertEqual((output / "_internal" / "library.dll").read_bytes(), b"dependency")
                with self.assertRaises(ValueError):
                    copy_bundle(source / "exports")


class NativeShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_playback_uses_a_local_url_for_paths_with_spaces_and_accents(self) -> None:
        from core.assistant_controller import AssistantController
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(directory=Path(directory))
            with patch("core.assistant_controller.Settings", return_value=settings):
                assistant = AssistantController()
            try:
                urls = []
                assistant.audioPathChanged.connect(urls.append)
                path = str(Path(directory) / "voix été.wav")
                assistant._on_speech_finished(path)
                self.assertEqual(QUrl(urls[0]).toLocalFile(), path)
                self.assertTrue(QUrl(urls[0]).isLocalFile())
            finally:
                assistant.shutdown()

    def test_windows_hold_repeat_and_main_key_release(self) -> None:
        from core.global_shortcut import shortcut_combination
        with patch("core.native_shortcut.sys.platform", "win32"):
            shortcut = NativeShortcut()
            shortcut._api = Mock()
            shortcut._api.RegisterHotKey.return_value = True
            shortcut.set_shortcut(shortcut_combination("Ctrl+Alt+Space"))
            self.assertEqual(shortcut._binding, (0x20, 3))
            events = []
            shortcut.pressed.connect(lambda: events.append("press"))
            shortcut.released.connect(lambda: events.append("release"))
            shortcut.activate()
            shortcut.activate()
            shortcut._api.GetAsyncKeyState.return_value = 0x8000
            shortcut._check_release()
            self.assertEqual(events, ["press"])
            shortcut._api.GetAsyncKeyState.return_value = 0
            shortcut._check_release()
            self.assertEqual(events, ["press", "release"])
            shortcut.shutdown()

    def test_export_service_uses_argument_list_and_rejects_cross_os(self) -> None:
        service = ExportService()
        with patch("core.export_service.QFileDialog.getExistingDirectory", return_value="/tmp/export destination") as choose, patch.object(
            service._process, "start"
        ) as start, patch("core.export_service.host_platform", return_value="linux"), patch(
            "core.export_service.importlib.util.find_spec", return_value=object()
        ):
            service.start("windows")
            choose.assert_not_called()
            service.start("linux")
            start.assert_called_once()
            self.assertIn("/tmp/export destination", service._process.arguments())
            self.assertIn("--platform", service._process.arguments())
            self.assertTrue(service.running)
        service._running = False
        service.shutdown()

    def test_windows_conflict_restores_previous_binding(self) -> None:
        from core.global_shortcut import shortcut_combination
        with patch("core.native_shortcut.sys.platform", "win32"):
            shortcut = NativeShortcut()
            shortcut._api = Mock()
            shortcut._binding = (0x20, 3)
            shortcut._api.RegisterHotKey.side_effect = [False, True]
            with self.assertRaisesRegex(RuntimeError, "already used"):
                shortcut.set_shortcut(shortcut_combination("Ctrl+F8"))
            self.assertEqual(shortcut._binding, (0x20, 3))
            shortcut.shutdown()

    def test_mac_uses_command_mapping_and_delivers_release(self) -> None:
        from core.global_shortcut import shortcut_combination
        with patch("core.native_shortcut.sys.platform", "darwin"):
            shortcut = NativeShortcut()
            shortcut._api = Mock()
            shortcut._api.GetApplicationEventTarget.return_value = None
            shortcut._api.RegisterEventHotKey.return_value = 0
            shortcut.set_shortcut(shortcut_combination("Ctrl+Alt+Space"))
            self.assertEqual(shortcut._binding, (49, 256 | 2048))
            events = []
            shortcut.pressed.connect(lambda: events.append("press"))
            shortcut.released.connect(lambda: events.append("release"))
            shortcut.activate()
            shortcut.release()
            self.assertEqual(events, ["press", "release"])
            shortcut.shutdown()
