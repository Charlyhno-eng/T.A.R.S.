from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Qt, Signal, QMetaObject, QUrl, QCoreApplication, QEvent, QPointF
from PySide6.QtGui import QKeySequence, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from Xlib import X

from core.desktop_service import DesktopService
from core.assistant_controller import AssistantController
from core.global_shortcut import GlobalShortcut, keysym_for_key, shortcut_combination
from core.settings import Settings


class GlobalShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_shortcuts_cannot_intercept_ordinary_typing(self) -> None:
        for text in ("A", "Shift+A", "Ctrl", "Esc", "Ctrl+A, Ctrl+B", ""):
            with self.subTest(text=text), self.assertRaises(ValueError):
                shortcut_combination(text)
        for text in ("Ctrl+Alt+Space", "Meta+V", "F8", "Ctrl+Shift+F12"):
            with self.subTest(text=text):
                combination = shortcut_combination(text)
                self.assertEqual(QKeySequence(combination).toString(QKeySequence.PortableText), text)
        self.assertEqual(keysym_for_key(Qt.Key_Space), 0x20)
        self.assertEqual(keysym_for_key(Qt.Key_A), ord("a"))
        self.assertEqual(keysym_for_key(Qt.Key_F8), 0xFFC5)

    def test_repeat_does_not_restart_or_finish_recording(self) -> None:
        hotkey = GlobalShortcut()
        hotkey._binding = (65, X.ControlMask)
        events = []
        hotkey.pressed.connect(lambda: events.append("press"))
        hotkey.released.connect(lambda: events.append("release"))
        press = SimpleNamespace(type=X.KeyPress, detail=65)
        release = SimpleNamespace(type=X.KeyRelease, detail=65)
        hotkey._handle_event(press)
        hotkey._handle_event(release)
        hotkey._handle_event(press)  # X11 auto-repeat pair.
        self.assertFalse(hotkey._release_timer.isActive())
        hotkey._handle_event(SimpleNamespace(type=X.KeyRelease, detail=37))
        self.assertEqual(events, ["press"])
        hotkey._handle_event(release)
        hotkey._release()
        self.assertEqual(events, ["press", "release"])
        hotkey.shutdown()

    def test_conflicting_shortcut_restores_previous_grab(self) -> None:
        hotkey = GlobalShortcut()
        hotkey._display = Mock()
        hotkey._display.keysym_to_keycode.return_value = 65
        hotkey._display.pending_events.return_value = 0
        old = (56, X.ControlMask)
        hotkey._binding = old
        with patch.object(hotkey, "_remove_grabs") as ungrab, patch.object(
            hotkey, "_grab", side_effect=[False, True]
        ) as grab:
            with self.assertRaisesRegex(RuntimeError, "already used"):
                hotkey.set_shortcut("Ctrl+Alt+Space")
            ungrab.assert_called_once_with(old)
            self.assertEqual(grab.call_args_list[-1].args, (old,))
            self.assertEqual(hotkey._binding, old)
        hotkey.shutdown()

    def test_lock_variants_are_removed_after_partial_conflict(self) -> None:
        hotkey = GlobalShortcut()
        hotkey._display = Mock()
        hotkey._root = Mock()
        hotkey._lock_masks = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]

        def conflict(*args, **kwargs):
            if args[1] & X.Mod2Mask:
                kwargs["onerror"](RuntimeError("busy"), None)

        hotkey._root.grab_key.side_effect = conflict
        self.assertFalse(hotkey._grab((65, X.ControlMask)))
        self.assertEqual(hotkey._root.grab_key.call_count, 4)
        self.assertEqual(hotkey._root.ungrab_key.call_count, 4)
        hotkey.shutdown()


class FakeAssistant(QObject):
    languageChanged = Signal()
    statusChanged = Signal()
    language = "en"
    status = "Ready"
    state = "idle"

    def __init__(self) -> None:
        super().__init__()
        self.calls = []
        self.ready = True

    def startListening(self) -> None:
        self.calls.append("start")
        if self.ready:
            self.state = "listening"

    def stopListening(self) -> None:
        self.calls.append("stop")
        self.state = "thinking"


class FakeHotkey(QObject):
    pressed = Signal()
    released = Signal()
    failed = Signal(str)

    @staticmethod
    def supported() -> bool:
        return True

    def set_shortcut(self, text: str) -> None:
        if text == "Ctrl+F9":
            raise RuntimeError("This shortcut is already used by another application.")

    def shutdown(self) -> None:
        pass


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings(directory=Path(self.directory.name))
        self.settings._path = Path(self.directory.name) / "config.toml"
        self.assistant = FakeAssistant()
        self.hotkey = FakeHotkey()
        self.tray_patcher = patch("core.desktop_service.QSystemTrayIcon")
        self.tray = self.tray_patcher.start()
        self.addCleanup(self.tray_patcher.stop)
        self.tray.isSystemTrayAvailable.return_value = True
        hotkey_patcher = patch("core.desktop_service.GlobalShortcut", return_value=self.hotkey)
        hotkey_class = hotkey_patcher.start()
        hotkey_class.supported.return_value = True
        self.addCleanup(hotkey_patcher.stop)
        with patch("core.desktop_service.Settings", return_value=self.settings):
            self.desktop = DesktopService(self.app, self.assistant, Path("assets/tars-mascot.png"))
        self.window = Mock()
        self.window.isVisible.return_value = False
        self.desktop.attach_window(self.window)
        self.window.reset_mock()
        self.addCleanup(self.desktop.shutdown)

    def test_startup_geometry_and_fullscreen_are_restored(self) -> None:
        self.assertTrue(self.desktop.saveWindowStartup(True, 1200, 800, -100, 50))
        window = Mock()
        self.desktop.attach_window(window)
        window.resize.assert_called_once_with(1200, 800)
        window.setPosition.assert_called_once_with(-100, 50)
        window.showFullScreen.assert_called_once()
        window.visibility.return_value = QWindow.Visibility.FullScreen
        self.desktop.hideToTray()
        self.desktop.showWindow()
        self.assertEqual(window.showFullScreen.call_count, 2)
        window.showNormal.assert_not_called()

    def test_failed_window_save_keeps_previous_preferences(self) -> None:
        original = self.desktop.windowStartup
        with patch.object(self.settings, "set_window_startup", side_effect=OSError):
            self.assertFalse(self.desktop.saveWindowStartup(True, 1200, 800, 0, 0))
        self.assertEqual(self.desktop.windowStartup, original)

    def test_close_hides_and_tray_reopens_window(self) -> None:
        self.assertTrue(self.desktop.hideToTray())
        self.window.hide.assert_called_once()
        self.desktop.showWindow()
        self.window.showNormal.assert_called_once()
        self.window.requestActivate.assert_called_once()
        self.assertFalse(self.app.quitOnLastWindowClosed())

    def test_missing_tray_leaves_normal_close_behavior(self) -> None:
        self.tray.isSystemTrayAvailable.return_value = False
        self.assertFalse(self.desktop.hideToTray())
        self.window.hide.assert_not_called()
        self.assertTrue(self.app.quitOnLastWindowClosed())
        self.window.showNormal.assert_called_once()

    def test_explicit_quit_is_not_intercepted_as_hide(self) -> None:
        with patch.object(self.app, "quit") as quit_app:
            self.desktop.quit()
            quit_app.assert_called_once()
        self.assertFalse(self.desktop.hideToTray())
        self.window.hide.assert_not_called()

    def test_hidden_shortcut_drives_existing_voice_pipeline(self) -> None:
        self.hotkey.pressed.emit()
        self.hotkey.released.emit()
        self.assertEqual(self.assistant.calls, ["start", "stop"])
        self.assertEqual(self.assistant.state, "thinking")
        self.hotkey.pressed.emit()  # Busy: no second request.
        self.hotkey.released.emit()
        self.assertEqual(self.assistant.calls, ["start", "stop"])

    def test_release_does_not_stop_mouse_or_unavailable_recording(self) -> None:
        self.assistant.state = "listening"  # Started with the central control.
        self.hotkey.pressed.emit()
        self.hotkey.released.emit()
        self.assertEqual(self.assistant.calls, [])
        self.assistant.state = "idle"
        self.assistant.ready = False
        self.hotkey.pressed.emit()
        self.hotkey.released.emit()
        self.assertEqual(self.assistant.calls, ["start"])

    def test_capture_does_not_record_and_conflict_does_not_change_preference(self) -> None:
        self.assertTrue(self.desktop.saveShortcut("Ctrl+Alt+Space"))
        self.desktop.beginShortcutCapture()
        self.hotkey.pressed.emit()
        self.hotkey.released.emit()
        self.assertEqual(self.assistant.calls, [])
        self.assertFalse(self.desktop.saveShortcut("Ctrl+F9"))
        self.assertEqual(self.desktop.shortcut, "Ctrl+Alt+Space")
        self.assertEqual(self.settings.shortcut(), "Ctrl+Alt+Space")
        self.assertIn("already used", self.desktop.shortcutError)
        self.desktop.endShortcutCapture()
        self.assertTrue(self.desktop.saveShortcut(""))
        self.assertEqual(self.settings.shortcut(), "")

    def test_failed_save_restores_previous_shortcut(self) -> None:
        self.assertTrue(self.desktop.saveShortcut("Ctrl+Alt+Space"))
        with patch.object(self.settings, "set_shortcut", side_effect=OSError("read only")), patch.object(
            self.hotkey, "set_shortcut"
        ) as register:
            self.assertFalse(self.desktop.saveShortcut("Ctrl+F8"))
            self.assertEqual(register.call_args_list[-1].args, ("Ctrl+Alt+Space",))
        self.assertEqual(self.desktop.shortcut, "Ctrl+Alt+Space")
        self.assertIn("Could not save", self.desktop.shortcutError)

    def test_frameless_close_button_preserves_tray_and_fullscreen_behavior(self) -> None:
        self.settings._key_path = Path(self.directory.name) / "llm_api_key"
        with patch("core.assistant_controller.Settings", return_value=self.settings):
            assistant = AssistantController()
        from core.export_service import ExportService
        exporter = ExportService()
        engine = QQmlApplicationEngine()
        ui_directory = Path(__file__).resolve().parents[1] / "src" / "ui"
        engine.addImportPath(str(ui_directory))
        for name, value in (("assistant", assistant), ("desktop", self.desktop),
                            ("exporter", exporter)):
            engine.rootContext().setContextProperty(name, value)
        warnings = []
        engine.warnings.connect(lambda errors: warnings.extend(str(error) for error in errors))
        engine.load(QUrl.fromLocalFile(str(ui_directory / "Main.qml")))
        try:
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            self.desktop.attach_window(window)
            self.assertTrue(window.flags() & Qt.FramelessWindowHint)
            self.assertIsNotNone(window.findChild(QObject, "assistantRobot"))
            self.assertIsNotNone(window.findChild(QObject, "assistantBackground"))
            button = window.findChild(QObject, "closeWindowButton")
            self.assertIsNotNone(button)

            def click_close():
                QTest.qWait(50)
                point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
                QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
                QTest.qWait(50)
                self.assertFalse(window.isVisible())
                self.assertIsNone(window.findChild(QObject, "assistantRobot"))
                self.assertIsNone(window.findChild(QObject, "assistantBackground"))
                self.assertTrue(assistant._tts_service._standby._background)
                self.assertTrue(assistant._stt_service._standby._background)

            window.showFullScreen()
            click_close()
            self.desktop.showWindow()
            self.assertEqual(window.visibility(), QWindow.FullScreen)
            self.assertIsNotNone(window.findChild(QObject, "assistantRobot"))
            self.assertFalse(assistant._tts_service._standby._background)
            self.assertFalse(assistant._stt_service._standby._background)
            window.showMinimized()
            QTest.qWait(50)
            self.assertTrue(assistant._tts_service._standby._background)
            self.assertTrue(assistant._stt_service._standby._background)
            self.assertIsNone(window.findChild(QObject, "assistantRobot"))
            self.assertIsNone(window.findChild(QObject, "assistantBackground"))
            self.assertFalse(self.app.quitOnLastWindowClosed())
            window.showNormal()
            self.tray.isSystemTrayAvailable.return_value = False
            click_close()
            self.assertTrue(self.app.quitOnLastWindowClosed())
            self.assertEqual(warnings, [])
        finally:
            engine.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assistant.shutdown()

    def test_qml_capture_saves_keys_and_escape_restores_recording(self) -> None:
        self.settings._key_path = Path(self.directory.name) / "llm_api_key"
        with patch("core.assistant_controller.Settings", return_value=self.settings):
            assistant = AssistantController()
        engine = QQmlApplicationEngine()
        ui_directory = Path(__file__).resolve().parents[1] / "src" / "ui"
        engine.addImportPath(str(ui_directory))
        engine.rootContext().setContextProperty("assistant", assistant)
        engine.rootContext().setContextProperty("desktop", self.desktop)
        from core.export_service import ExportService
        exporter = ExportService()
        engine.rootContext().setContextProperty("exporter", exporter)
        warnings = []
        engine.warnings.connect(lambda errors: warnings.extend(str(error) for error in errors))
        engine.loadData(f'''
            import QtQuick
            import QtQuick.Controls
            import "{(ui_directory / 'components').as_uri()}"
            ApplicationWindow {{
                width: 760; height: 560; visible: true
                SettingsDialog {{ anchors.centerIn: parent }}
            }}
        '''.encode())
        try:
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            settings = window.findChild(QObject, "settingsDialog")
            shortcut = window.findChild(QObject, "shortcutDialog")
            QMetaObject.invokeMethod(settings, "open")
            QTest.qWait(150)
            self.assertLessEqual(settings.property("height"), 512)
            QMetaObject.invokeMethod(shortcut, "open")
            QTest.qWait(150)
            QTest.keyClick(window, Qt.Key_Space, Qt.ControlModifier | Qt.AltModifier)
            self.assertEqual(shortcut.property("candidate"), "Ctrl+Alt+Space")
            self.assertTrue(self.desktop._capturing)
            self.assertTrue(self.desktop.saveShortcut(shortcut.property("candidate")))
            QTest.keyClick(window, Qt.Key_Escape)
            QTest.qWait(150)
            self.assertFalse(shortcut.property("visible"))
            self.assertFalse(self.desktop._capturing)
            self.assertEqual(self.settings.shortcut(), "Ctrl+Alt+Space")
            export_dialog = window.findChild(QObject, "exportDialog")
            QMetaObject.invokeMethod(export_dialog, "open")
            QTest.qWait(150)
            target = window.findChild(QObject, "exportTarget")
            self.assertEqual(target.property("model"), ["Linux", "Windows", "macOS"])
            self.assertEqual(target.property("currentIndex"),
                             ["linux", "windows", "macos"].index(exporter.platform))
            QMetaObject.invokeMethod(export_dialog, "close")
            QMetaObject.invokeMethod(settings, "close")
            QTest.qWait(150)
            self.assertEqual(warnings, [])
        finally:
            # Destroy QML before its context properties, avoiding teardown warnings.
            engine.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assistant.shutdown()

    def test_settings_download_is_visible_and_installs_only_missing_models(self) -> None:
        self.settings._key_path = Path(self.directory.name) / "llm_api_key"
        with patch("core.assistant_controller.Settings", return_value=self.settings):
            assistant = AssistantController()
        from core.export_service import ExportService
        exporter = ExportService()
        engine = QQmlApplicationEngine()
        ui_directory = Path(__file__).resolve().parents[1] / "src" / "ui"
        engine.addImportPath(str(ui_directory))
        for name, value in (("assistant", assistant), ("desktop", self.desktop),
                            ("exporter", exporter)):
            engine.rootContext().setContextProperty(name, value)
        warnings = []
        engine.warnings.connect(lambda errors: warnings.extend(str(error) for error in errors))
        try:
            with (
                patch.object(type(assistant._tts_service), "installed", new_callable=PropertyMock) as tts_installed,
                patch.object(type(assistant._stt_service), "installed", new_callable=PropertyMock) as stt_installed,
                patch.object(assistant._tts_service, "download") as tts_download,
                patch.object(assistant._stt_service, "download") as stt_download,
            ):
                tts_installed.return_value = stt_installed.return_value = False
                engine.loadData(f'''
                    import QtQuick
                    import QtQuick.Controls
                    import "{(ui_directory / 'components').as_uri()}"
                    ApplicationWindow {{
                        width: 600; height: 560; visible: true
                        SettingsDialog {{ anchors.centerIn: parent }}
                    }}
                '''.encode())
                self.assertTrue(engine.rootObjects())
                window = engine.rootObjects()[0]
                settings = window.findChild(QObject, "settingsDialog")
                button = window.findChild(QObject, "downloadModelsButton")
                voice_status = window.findChild(QObject, "ttsModelStatus")
                recognition_status = window.findChild(QObject, "sttModelStatus")
                self.assertIsNotNone(button)

                def click_download():
                    point = button.mapToScene(QPointF(button.width() / 2, button.height() / 2))
                    # The whole control must be reachable without scrolling at minimum size.
                    self.assertGreaterEqual(point.y() - button.height() / 2, settings.property("y"))
                    self.assertLessEqual(point.y() + button.height() / 2,
                                         settings.property("y") + settings.property("height"))
                    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, point.toPoint())
                    QTest.qWait(20)

                for language, voice in (("en", "English"), ("fr", "Français")):
                    with self.subTest(language=language):
                        tts_installed.return_value = stt_installed.return_value = False
                        assistant.modelsInstalledChanged.emit()
                        assistant.setLanguage(language)
                        tts_download.reset_mock()
                        stt_download.reset_mock()
                        QMetaObject.invokeMethod(settings, "open")
                        QTest.qWait(150)
                        self.assertTrue(button.property("visible"))
                        self.assertTrue(button.property("enabled"))
                        self.assertIn(voice, voice_status.property("text"))
                        click_download()
                        tts_download.assert_called_once()
                        stt_download.assert_not_called()
                        self.assertTrue(assistant.modelsDownloading)
                        self.assertFalse(button.property("enabled"))

                        # Failure restores the action, and an existing voice is kept.
                        assistant._on_model_installation_failed()
                        self.assertTrue(button.property("enabled"))
                        tts_installed.return_value = True
                        assistant.modelsInstalledChanged.emit()
                        click_download()
                        tts_download.assert_called_once()
                        stt_download.assert_called_once()
                        stt_installed.return_value = True
                        assistant._on_tts_state_changed("ready")
                        assistant._on_stt_state_changed("ready")
                        assistant._on_stt_installed()
                        QTest.qWait(20)
                        self.assertFalse(assistant.modelsDownloading)
                        self.assertTrue(assistant.modelsInstalled)
                        self.assertFalse(button.property("enabled"))
                        self.assertIn("Installed" if language == "en" else "Installée",
                                      voice_status.property("text"))
                        self.assertIn("Installed" if language == "en" else "Installé",
                                      recognition_status.property("text"))
                        QMetaObject.invokeMethod(settings, "close")
                        QTest.qWait(100)
                self.assertEqual(warnings, [])
        finally:
            engine.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
            assistant.shutdown()
            exporter.shutdown()
