from __future__ import annotations

import ctypes
from ctypes import wintypes
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt
from Xlib import X

from backend_support import BackendTestCase
from core.global_shortcut import GlobalShortcut, keysym_for_key, shortcut_combination
from core.native_shortcut import HotKeyID, NativeShortcut, mac_character_keycode


class ShortcutBackendTests(BackendTestCase):
    def test_windows_native_registration_event_filter_and_layout_validation(self):
        api = Mock()
        with patch("core.native_shortcut.sys.platform", "win32"), patch(
            "core.native_shortcut.ctypes.WinDLL", return_value=api, create=True
        ):
            shortcut = NativeShortcut()
            self.addCleanup(shortcut.shutdown)
            shortcut.set_shortcut(shortcut_combination("Ctrl+F8"))
            shortcut._connect()  # Reuse the native connection.
            self.assertEqual(shortcut._binding, (0x77, 2))
            api.VkKeyScanW.return_value = 0x141
            self.assertEqual(shortcut._keycode(Qt.Key_A), 0x41)
            api.VkKeyScanW.return_value = -1
            with self.assertRaises(ValueError):
                shortcut._keycode(Qt.Key_A)
            with self.assertRaises(ValueError):
                shortcut._keycode(Qt.Key_unknown)
            event = wintypes.MSG()
            event.message, event.wParam = 0x0312, shortcut.identifier
            self.assertEqual(shortcut._filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(event)), (True, 0))
            self.assertTrue(shortcut._held)
            event.wParam += 1
            self.assertEqual(shortcut._filter.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(event)), (False, 0))
            shortcut.set_shortcut(None)
            self.assertFalse(shortcut._held)
            self.assertIsNone(shortcut._binding)
            shortcut.shutdown()
            self.assertIsNone(shortcut._filter)

    def test_native_connection_errors_become_runtime_errors(self):
        shortcut = NativeShortcut()
        with patch.object(shortcut, "_connect", side_effect=OSError("Missing API")):
            with self.assertRaisesRegex(RuntimeError, "desktop"):
                shortcut.set_shortcut(shortcut_combination("Ctrl+F8"))

    def test_mac_callback_checks_ownership_and_cleans_up_handler(self):
        api = Mock()
        api.InstallEventHandler.return_value = 0
        api.GetEventKind.return_value = 5

        def identifier(event, name, kind, unused, size, output_size, result):
            pointer = ctypes.cast(result, ctypes.POINTER(HotKeyID))
            pointer.contents.signature = 0x54415253
            pointer.contents.id = shortcut.identifier
            return 0

        api.GetEventParameter.side_effect = identifier
        with patch("core.native_shortcut.sys.platform", "darwin"), patch(
            "core.native_shortcut.ctypes.CDLL", return_value=api
        ):
            shortcut = NativeShortcut()
            shortcut._connect()
            shortcut._binding = (49, 256)
            self.assertEqual(shortcut._callback(None, None, None), 0)
            self.assertTrue(shortcut._held)
            api.GetEventKind.return_value = 6
            self.assertEqual(shortcut._callback(None, None, None), 0)
            self.assertFalse(shortcut._held)
            api.GetEventParameter.side_effect = None
            api.GetEventParameter.return_value = 1
            self.assertEqual(shortcut._callback(None, None, None), -9874)
            self.assertEqual(shortcut._keycode(Qt.Key_F1), 122)
            with patch("core.native_shortcut.mac_character_keycode", return_value=0) as keycode:
                self.assertEqual(shortcut._keycode(Qt.Key_A), 0)
                keycode.assert_called_once_with("a")
            shortcut._handler = ctypes.c_void_p(42)
            shortcut.shutdown()
            api.RemoveEventHandler.assert_called_once()
            api.InstallEventHandler.return_value = 1
            with self.assertRaisesRegex(RuntimeError, "desktop"):
                NativeShortcut()._connect()

    def test_x11_modifier_mapping_grab_release_and_disconnect(self):
        display = Mock()
        display.keysym_to_keycode.return_value = 65
        display.get_modifier_mapping.return_value = [[], [], [], [], [65], [], [], []]
        display.pending_events.return_value = 0
        with patch.object(GlobalShortcut, "supported", return_value=True), patch(
            "Xlib.display.Display", return_value=display
        ):
            shortcut = GlobalShortcut()
            self.addCleanup(shortcut.shutdown)
            shortcut.set_shortcut("Ctrl+Alt+Shift+F8")
            self.assertEqual(set(shortcut._lock_masks), {0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask})
            self.assertEqual(shortcut._binding, (65, X.ControlMask | X.Mod1Mask | X.ShiftMask))
            shortcut._connect()
            released, errors = [], []
            shortcut.released.connect(lambda: released.append(True))
            shortcut.failed.connect(errors.append)
            display.pending_events.side_effect = [1, 0]
            display.next_event.return_value = SimpleNamespace(type=X.KeyPress, detail=65)
            shortcut._poll()
            self.assertTrue(shortcut._pressed)
            display.pending_events.side_effect = RuntimeError("Disconnected")
            shortcut._poll()
            self.assertEqual(released, [True])
            self.assertEqual(len(errors), 1)
            self.assertIsNone(shortcut._display)
            display.close.assert_called_once()

    def test_x11_connection_and_unavailable_key_fail_without_grabs(self):
        shortcut = GlobalShortcut()
        self.addCleanup(shortcut.shutdown)
        with patch.object(shortcut, "supported", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "X11"):
                shortcut.set_shortcut("Ctrl+F8")
        with patch.object(shortcut, "supported", return_value=True), patch(
            "Xlib.display.Display", side_effect=OSError("No display")
        ):
            with self.assertRaisesRegex(RuntimeError, "connect"):
                shortcut.set_shortcut("Ctrl+F8")
        shortcut._display = Mock()
        shortcut._display.keysym_to_keycode.return_value = 0
        with self.assertRaises(ValueError):
            shortcut.set_shortcut("Ctrl+F8")
        shortcut._display.close.side_effect = OSError("Already closed")
        shortcut.shutdown()
        self.assertIsNone(shortcut._display)
        self.assertEqual(keysym_for_key(Qt.Key_Eacute), ord("é"))
        self.assertEqual(keysym_for_key(0x20AC), 0x010020AC)
        with self.assertRaises(ValueError):
            keysym_for_key(Qt.Key_unknown)

    def test_global_shortcut_routes_native_signals_and_shutdown(self):
        with patch("core.global_shortcut.sys.platform", "win32"):
            shortcut = GlobalShortcut()
            native = shortcut._native
            with patch.object(native, "set_shortcut") as register, patch.object(native, "shutdown") as shutdown:
                self.assertTrue(shortcut.supported())
                shortcut.set_shortcut("Ctrl+F8")
                self.assertEqual(register.call_args.args[0].key(), Qt.Key_F8)
                shortcut.set_shortcut("")
                register.assert_called_with(None)
                shortcut.shutdown()
                shutdown.assert_called_once()

    def test_mac_keyboard_layout_translation_and_failure_release_source(self):
        for failure in (None, "missing_layout", "missing_key"):
            with self.subTest(failure=failure):
                carbon, core = Mock(), Mock()
                carbon.TISCopyCurrentKeyboardLayoutInputSource.return_value = 12
                carbon.TISGetInputSourceProperty.return_value = None if failure == "missing_layout" else 24
                carbon.LMGetKbdType.return_value = 0
                core.CFDataGetBytePtr.return_value = 36

                def translate(layout, code, action, modifiers, keyboard, options,
                              dead, maximum, length, chars):
                    if code == 3 and failure != "missing_key":
                        ctypes.cast(length, ctypes.POINTER(ctypes.c_uint32)).contents.value = 1
                        chars[0] = ord("a")
                        return 0
                    return 1

                carbon.UCKeyTranslate.side_effect = translate
                with patch("core.native_shortcut.ctypes.CDLL", side_effect=[carbon, core]), patch(
                    "core.native_shortcut.ctypes.c_void_p.in_dll", return_value=ctypes.c_void_p(5)
                ):
                    if failure:
                        with self.assertRaisesRegex(ValueError, "keyboard layout"):
                            mac_character_keycode("a")
                    else:
                        self.assertEqual(mac_character_keycode("a"), 3)
                core.CFRelease.assert_called_once_with(12)
