"""Native registered shortcuts on Windows and macOS, without a keyboard listener."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import itertools

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, QTimer, Qt, Signal


SPECIAL_KEYS = {
    Qt.Key_Space: (0x20, 49), Qt.Key_Tab: (0x09, 48),
    Qt.Key_Return: (0x0D, 36), Qt.Key_Backspace: (0x08, 51),
    Qt.Key_Delete: (0x2E, 117), Qt.Key_Insert: (0x2D, 114),
    Qt.Key_Home: (0x24, 115), Qt.Key_End: (0x23, 119),
    Qt.Key_PageUp: (0x21, 116), Qt.Key_PageDown: (0x22, 121),
    Qt.Key_Left: (0x25, 123), Qt.Key_Right: (0x27, 124),
    Qt.Key_Down: (0x28, 125), Qt.Key_Up: (0x26, 126),
}
MAC_FUNCTION_KEYS = [122, 120, 99, 118, 96, 97, 98, 100, 101, 109,
                     103, 111, 105, 107, 113, 106, 64, 79, 80, 90]


class WindowsEventFilter(QAbstractNativeEventFilter):
    def __init__(self, shortcut) -> None:
        super().__init__()
        self.shortcut = shortcut

    def nativeEventFilter(self, event_type, message):
        event = wintypes.MSG.from_address(int(message))
        if event.message == 0x0312 and event.wParam == self.shortcut.identifier:
            self.shortcut.activate()
            return True, 0
        return False, 0


class NativeShortcut(QObject):
    pressed = Signal()
    released = Signal()
    _identifiers = itertools.count(1)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._binding = None
        self._held = False
        self._api = None
        self._reference = ctypes.c_void_p()
        self._handler = ctypes.c_void_p()
        self._callback = None
        self._filter = None
        # IDs belong to this instance so two app services cannot unregister
        # each other's shortcut within the same process.
        self.identifier = next(self._identifiers)
        self._timer = QTimer(self)
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._check_release)

    def _connect(self) -> None:
        if self._api is not None:
            return
        if sys.platform == "win32":
            self._api = ctypes.WinDLL("user32", use_last_error=True)
            self._api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
            self._api.RegisterHotKey.restype = wintypes.BOOL
            self._api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self._api.UnregisterHotKey.restype = wintypes.BOOL
            self._api.GetAsyncKeyState.argtypes = [ctypes.c_int]
            self._api.GetAsyncKeyState.restype = ctypes.c_short
            self._api.VkKeyScanW.argtypes = [wintypes.WCHAR]
            self._api.VkKeyScanW.restype = ctypes.c_short
            self._filter = WindowsEventFilter(self)
            QCoreApplication.instance().installNativeEventFilter(self._filter)
        else:
            self._connect_mac()

    def _connect_mac(self) -> None:
        self._api = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        self._api.GetApplicationEventTarget.restype = ctypes.c_void_p
        self._api.GetEventKind.argtypes = [ctypes.c_void_p]
        self._api.GetEventKind.restype = ctypes.c_uint32
        self._api.GetEventParameter.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
            ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
        self._api.GetEventParameter.restype = ctypes.c_int32
        self._api.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
            HotKeyID, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        self._api.RegisterEventHotKey.restype = ctypes.c_int32
        self._api.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        self._api.UnregisterEventHotKey.restype = ctypes.c_int32
        self._api.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        self._api.RemoveEventHandler.restype = ctypes.c_int32
        callback_type = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

        def event_handler(call, event, data):
            identifier = HotKeyID()
            result = self._api.GetEventParameter(event, 0x2D2D2D2D, 0x686B6964,
                None, ctypes.sizeof(identifier), None, ctypes.byref(identifier))
            if result or identifier.signature != 0x54415253 or identifier.id != self.identifier:
                return -9874  # eventNotHandledErr; leave other handlers alone.
            if self._api.GetEventKind(event) == 5:
                self.activate()
            else:
                self.release()
            return 0

        self._callback = callback_type(event_handler)
        events = (EventType * 2)(EventType(0x6B657962, 5), EventType(0x6B657962, 6))
        self._api.InstallEventHandler.argtypes = [ctypes.c_void_p, callback_type,
            ctypes.c_uint32, ctypes.POINTER(EventType), ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        self._api.InstallEventHandler.restype = ctypes.c_int32
        result = self._api.InstallEventHandler(self._api.GetApplicationEventTarget(),
            self._callback, 2, events, None, ctypes.byref(self._handler))
        if result:
            self._api = None
            raise RuntimeError("Could not register a shortcut with the desktop.")

    def _keycode(self, key: Qt.Key) -> int:
        if key in SPECIAL_KEYS:
            return SPECIAL_KEYS[key][0 if sys.platform == "win32" else 1]
        if Qt.Key_F1 <= key <= Qt.Key_F35:
            index = int(key) - int(Qt.Key_F1)
            if sys.platform == "win32" and index < 24:
                return 0x70 + index
            if sys.platform == "darwin" and index < len(MAC_FUNCTION_KEYS):
                return MAC_FUNCTION_KEYS[index]
        if 0x21 <= int(key) <= 0xFFFF:
            if sys.platform == "win32":
                code = self._api.VkKeyScanW(chr(int(key)))
                if code != -1:
                    return code & 0xFF
            else:
                return mac_character_keycode(chr(int(key)).lower())
        raise ValueError("This key is unavailable in the current keyboard layout.")

    def set_shortcut(self, combination) -> None:
        new_binding = None
        if combination is not None:
            try:
                self._connect()
            except OSError as exc:
                raise RuntimeError("Could not register a shortcut with the desktop.") from exc
            code = self._keycode(combination.key())
            modifiers = combination.keyboardModifiers()
            mapping = ((Qt.ControlModifier, 2, 256), (Qt.AltModifier, 1, 2048),
                       (Qt.ShiftModifier, 4, 512), (Qt.MetaModifier, 8, 4096))
            mask = sum(windows if sys.platform == "win32" else mac
                       for qt, windows, mac in mapping if modifiers & qt)
            new_binding = (code, mask)
        old_binding = self._binding
        self._unregister()
        if new_binding:
            if not self._register(new_binding):
                if old_binding and self._register(old_binding):
                    self._binding = old_binding
                raise RuntimeError("This shortcut is already used by another application.")
            self._binding = new_binding

    def _register(self, binding) -> bool:
        if sys.platform == "win32":
            return bool(self._api.RegisterHotKey(None, self.identifier, binding[1] | 0x4000, binding[0]))
        return self._api.RegisterEventHotKey(binding[0], binding[1],
            HotKeyID(0x54415253, self.identifier), self._api.GetApplicationEventTarget(),
            0, ctypes.byref(self._reference)) == 0

    def _unregister(self) -> None:
        self.release()
        if self._binding:
            if sys.platform == "win32":
                self._api.UnregisterHotKey(None, self.identifier)
            else:
                self._api.UnregisterEventHotKey(self._reference)
            self._binding = None

    def activate(self) -> None:
        if self._binding and not self._held:
            self._held = True
            self.pressed.emit()
            if sys.platform == "win32":
                self._timer.start()

    def _check_release(self) -> None:
        if self._binding and not self._api.GetAsyncKeyState(self._binding[0]) & 0x8000:
            self.release()

    def release(self) -> None:
        self._timer.stop()
        if self._held:
            self._held = False
            self.released.emit()

    def shutdown(self) -> None:
        self._unregister()
        if self._filter:
            QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None
        if self._handler.value:
            self._api.RemoveEventHandler(self._handler)
            self._handler = ctypes.c_void_p()
        self._api = None


class HotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


class EventType(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


def mac_character_keycode(character: str) -> int:
    """Use the current macOS layout rather than assuming a US keyboard."""
    carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
    core = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    carbon.TISCopyCurrentKeyboardLayoutInputSource.restype = ctypes.c_void_p
    carbon.TISGetInputSourceProperty.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    carbon.TISGetInputSourceProperty.restype = ctypes.c_void_p
    core.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
    core.CFDataGetBytePtr.restype = ctypes.c_void_p
    core.CFRelease.argtypes = [ctypes.c_void_p]
    source = carbon.TISCopyCurrentKeyboardLayoutInputSource()
    try:
        prop = ctypes.c_void_p.in_dll(carbon, "kTISPropertyUnicodeKeyLayoutData")
        data = carbon.TISGetInputSourceProperty(source, prop)
        if not data:
            raise ValueError("This key is unavailable in the current keyboard layout.")
        layout = core.CFDataGetBytePtr(data)
        carbon.LMGetKbdType.restype = ctypes.c_uint8
        carbon.UCKeyTranslate.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16,
            ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(ctypes.c_uint16)]
        carbon.UCKeyTranslate.restype = ctypes.c_int32
        for code in range(128):
            for modifiers in (0, 2):  # Unshifted and shifted symbols.
                dead, length = ctypes.c_uint32(), ctypes.c_uint32()
                chars = (ctypes.c_uint16 * 4)()
                status = carbon.UCKeyTranslate(layout, code, 0, modifiers,
                    carbon.LMGetKbdType(), 1, ctypes.byref(dead), 4, ctypes.byref(length), chars)
                if status == 0 and length.value == 1 and chr(chars[0]).lower() == character:
                    return code
    finally:
        if source:
            core.CFRelease(source)
    raise ValueError("This key is unavailable in the current keyboard layout.")
