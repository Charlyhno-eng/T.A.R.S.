from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence


def shortcut_combination(text: str):
    """Accept a single modified key or function key, never ordinary typing."""
    sequence = QKeySequence.fromString(text, QKeySequence.PortableText)
    if sequence.count() != 1:
        raise ValueError("Choose a single key combination.")
    combination = sequence[0]
    key = combination.key()
    modifiers = combination.keyboardModifiers()
    if key in (Qt.Key_unknown, Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt,
               Qt.Key_Meta, Qt.Key_AltGr, Qt.Key_Escape):
        raise ValueError("Choose a key with Ctrl, Alt or Super, or a function key.")
    if not modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier):
        if not Qt.Key_F1 <= key <= Qt.Key_F35:
            raise ValueError("Choose a key with Ctrl, Alt or Super, or a function key.")
    if modifiers & (Qt.KeypadModifier | Qt.GroupSwitchModifier):
        raise ValueError("Keypad and AltGr shortcuts are not supported.")
    return combination


def keysym_for_key(key: Qt.Key) -> int:
    """Map Qt keys to X11 key symbols, including non-US letter keys."""
    from Xlib import XK

    names = {
        Qt.Key_Space: "space", Qt.Key_Tab: "Tab", Qt.Key_Backtab: "Tab",
        Qt.Key_Backspace: "BackSpace", Qt.Key_Return: "Return",
        Qt.Key_Insert: "Insert", Qt.Key_Delete: "Delete",
        Qt.Key_Pause: "Pause", Qt.Key_Print: "Print",
        Qt.Key_Home: "Home", Qt.Key_End: "End",
        Qt.Key_Left: "Left", Qt.Key_Up: "Up", Qt.Key_Right: "Right",
        Qt.Key_Down: "Down", Qt.Key_PageUp: "Prior", Qt.Key_PageDown: "Next",
        Qt.Key_Menu: "Menu",
    }
    if key in names:
        return XK.string_to_keysym(names[key])
    if Qt.Key_F1 <= key <= Qt.Key_F35:
        return XK.string_to_keysym(f"F{int(key) - int(Qt.Key_F1) + 1}")
    if 0x21 <= int(key) <= 0x10FFFF:
        character = chr(int(key)).lower()
        if len(character) == 1:
            value = ord(character)
            return value if value <= 0xFF else 0x01000000 | value
    raise ValueError("This key is not supported as a global shortcut.")


class GlobalShortcut(QObject):
    """Grab only the configured combination on an independent X11 connection."""

    pressed = Signal()
    released = Signal()
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._display = None
        self._root = None
        self._binding: tuple[int, int] | None = None
        self._lock_masks = [0]
        self._pressed = False
        self._native = None
        if sys.platform in ("win32", "darwin"):
            from core.native_shortcut import NativeShortcut
            self._native = NativeShortcut(self)
            self._native.pressed.connect(self.pressed.emit)
            self._native.released.connect(self.released.emit)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(20)
        self._poll_timer.timeout.connect(self._poll)
        # Traditional X11 repeat generates release/press pairs. Delay release
        # slightly so a repeated press can cancel it without ending recording.
        self._release_timer = QTimer(self)
        self._release_timer.setSingleShot(True)
        self._release_timer.setInterval(40)
        self._release_timer.timeout.connect(self._release)

    @staticmethod
    def supported() -> bool:
        return sys.platform in ("win32", "darwin") or (
            sys.platform.startswith("linux") and QGuiApplication.platformName() == "xcb")

    def _connect(self) -> None:
        if self._display is not None:
            return
        if not self.supported():
            raise RuntimeError("Global shortcuts require a Linux X11 session.")
        from Xlib import X, XK, display

        try:
            self._display = display.Display()
            self._root = self._display.screen().root
            # Ignore Caps Lock and the actual Num Lock modifier mapping.
            ignored = X.LockMask
            num_lock = self._display.keysym_to_keycode(XK.string_to_keysym("Num_Lock"))
            for index, codes in enumerate(self._display.get_modifier_mapping()):
                if num_lock and num_lock in codes:
                    ignored |= 1 << index
            bits = [1 << bit for bit in range(8) if ignored & (1 << bit)]
            self._lock_masks = [0]
            for bit in bits:
                self._lock_masks += [mask | bit for mask in self._lock_masks]
        except Exception as exc:
            self.shutdown()
            raise RuntimeError("Could not connect to the X11 desktop.") from exc

    def set_shortcut(self, text: str) -> None:
        """Replace a grab, restoring the previous one if the new key is busy."""
        if self._native is not None:
            self._native.set_shortcut(shortcut_combination(text) if text else None)
            return
        from Xlib import X

        new_binding = None
        if text:
            combination = shortcut_combination(text)
            self._connect()
            keycode = self._display.keysym_to_keycode(keysym_for_key(combination.key()))
            if not keycode:
                raise ValueError("This key is unavailable in the current keyboard layout.")
            modifiers = combination.keyboardModifiers()
            mask = 0
            for qt_mask, x_mask in (
                (Qt.ControlModifier, X.ControlMask), (Qt.ShiftModifier, X.ShiftMask),
                (Qt.AltModifier, X.Mod1Mask), (Qt.MetaModifier, X.Mod4Mask),
            ):
                if modifiers & qt_mask:
                    mask |= x_mask
            new_binding = (keycode, mask)
        old_binding = self._binding
        self._ungrab()
        if new_binding:
            if not self._grab(new_binding):
                if old_binding and self._grab(old_binding):
                    self._binding = old_binding
                    self._poll_timer.start()
                raise RuntimeError("This shortcut is already used by another application.")
            self._binding = new_binding
            self._poll_timer.start()

    def _grab(self, binding: tuple[int, int]) -> bool:
        from Xlib import X

        errors = []

        def on_error(error, request):
            errors.append(error)
            return True

        for lock_mask in self._lock_masks:
            self._root.grab_key(
                binding[0], binding[1] | lock_mask, False,
                X.GrabModeAsync, X.GrabModeAsync,
                onerror=on_error,
            )
        self._display.sync()
        if errors:
            self._remove_grabs(binding)
            return False
        return True

    def _remove_grabs(self, binding: tuple[int, int]) -> None:
        for lock_mask in self._lock_masks:
            self._root.ungrab_key(binding[0], binding[1] | lock_mask)
        self._display.sync()

    def _ungrab(self) -> None:
        self._poll_timer.stop()
        self._release()
        if self._binding:
            self._remove_grabs(self._binding)
            self._binding = None
        if self._display:
            # Discard queued events from the previous registration.
            while self._display.pending_events():
                self._display.next_event()

    def _poll(self) -> None:
        try:
            while self._display and self._display.pending_events():
                self._handle_event(self._display.next_event())
        except Exception:
            self.shutdown()
            self.failed.emit("The global shortcut connection was lost. Restart T.A.R.S.")

    def _handle_event(self, event) -> None:
        from Xlib import X

        if not self._binding or event.type not in (X.KeyPress, X.KeyRelease):
            return
        if event.detail != self._binding[0]:
            return
        if event.type == X.KeyPress:
            self._release_timer.stop()
            if not self._pressed:
                self._pressed = True
                self.pressed.emit()
        elif self._pressed:
            self._release_timer.start()

    def _release(self) -> None:
        self._release_timer.stop()
        if self._pressed:
            self._pressed = False
            self.released.emit()

    def shutdown(self) -> None:
        if self._native is not None:
            self._native.shutdown()
        self._poll_timer.stop()
        self._release()
        if self._display:
            try:
                self._display.close()  # Closing releases all X11 grabs.
            except Exception:
                pass
        self._display = None
        self._root = None
        self._binding = None
