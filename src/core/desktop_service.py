from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Qt, Signal, Slot, QKeyCombination
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core.global_shortcut import GlobalShortcut, shortcut_combination
from core.settings import Settings


class DesktopService(QObject):
    """Keep the assistant accessible through the tray and a global shortcut."""

    trayAvailableChanged = Signal()
    shortcutChanged = Signal()
    shortcutErrorChanged = Signal()

    FRENCH_ERRORS = {
        "Could not register a shortcut with the desktop.": "Impossible d'enregistrer le raccourci sur ce bureau.",
        "Global shortcuts require a Linux X11 session.": "Les raccourcis globaux nécessitent une session Linux X11.",
        "Could not connect to the X11 desktop.": "Impossible de se connecter au bureau X11.",
        "Choose a single key combination.": "Choisissez une seule combinaison de touches.",
        "Choose a key with Ctrl, Alt or Super, or a function key.": "Choisissez une touche avec Ctrl, Alt ou Super, ou une touche de fonction.",
        "Keypad and AltGr shortcuts are not supported.": "Les raccourcis du pavé numérique et AltGr ne sont pas pris en charge.",
        "This key is not supported as a global shortcut.": "Cette touche ne peut pas servir de raccourci global.",
        "This key is unavailable in the current keyboard layout.": "Cette touche est indisponible dans la disposition du clavier actuelle.",
        "This shortcut is already used by another application.": "Ce raccourci est déjà utilisé par une autre application.",
        "Could not save the shortcut settings.": "Impossible d'enregistrer le raccourci.",
        "The global shortcut connection was lost. Restart T.A.R.S.": "La connexion du raccourci global a été perdue. Relancez T.A.R.S.",
    }

    def __init__(self, app: QApplication, assistant, icon_path: Path) -> None:
        super().__init__(app)
        self._app = app
        self._assistant = assistant
        self._settings = Settings()
        self._window = None
        self._shortcut = self._settings.shortcut()
        self._error = ""
        self._capturing = False
        self._held = False
        self._notified_hidden = False
        self._quitting = False
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._hotkey = GlobalShortcut(self)
        self._hotkey.pressed.connect(self._on_pressed)
        self._hotkey.released.connect(self._on_released)
        self._hotkey.failed.connect(self._set_error)

        self._tray = QSystemTrayIcon(QIcon(str(icon_path)), self)
        self._menu = QMenu()
        self._open_action = self._menu.addAction("Open T.A.R.S.", self.showWindow)
        self._menu.addSeparator()
        self._quit_action = self._menu.addAction("Quit", self.quit)
        self._tray.setContextMenu(self._menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.messageClicked.connect(self.showWindow)
        self._tray.setVisible(self._tray_available)
        app.setQuitOnLastWindowClosed(not self._tray_available)
        assistant.languageChanged.connect(self._translate)
        assistant.statusChanged.connect(self._update_tooltip)
        self._translate()
        self._restore_shortcut()

        # XFCE may restart its panel while the assistant is running.
        self._tray_timer = QTimer(self)
        self._tray_timer.setInterval(2000)
        self._tray_timer.timeout.connect(self._refresh_tray)
        self._tray_timer.start()

    def attach_window(self, window) -> None:
        self._window = window

    @Property(bool, notify=trayAvailableChanged)
    def trayAvailable(self) -> bool:
        return self._tray_available

    @Property(bool, constant=True)
    def shortcutSupported(self) -> bool:
        return GlobalShortcut.supported()

    @Property(str, notify=shortcutChanged)
    def shortcut(self) -> str:
        return self._shortcut

    @Property(str, notify=shortcutErrorChanged)
    def shortcutError(self) -> str:
        if self._assistant.language == "fr":
            return self.FRENCH_ERRORS.get(self._error, self._error)
        return self._error

    @Slot()
    def showWindow(self) -> None:
        if self._window is not None:
            self._window.showNormal()
            self._window.raise_()
            self._window.requestActivate()

    @Slot(result=bool)
    def hideToTray(self) -> bool:
        if self._quitting:
            return False
        self._refresh_tray()
        if not self._tray_available:
            return False
        self._window.hide()
        if not self._notified_hidden:
            self._notify(
                "T.A.R.S. is still running. Hold your shortcut to speak; use the tray menu to quit."
                if self._assistant.language == "en" else
                "T.A.R.S. reste actif. Maintenez votre raccourci pour parler ; utilisez le menu de l'icône pour quitter."
            )
            self._notified_hidden = True
        return True

    @Slot()
    def quit(self) -> None:
        self._quitting = True
        self._app.quit()

    @Slot()
    def beginShortcutCapture(self) -> None:
        self._capturing = True
        self._set_error("")
        self._hotkey.set_shortcut("")

    @Slot()
    def endShortcutCapture(self) -> None:
        if self._capturing:
            self._capturing = False
            self._restore_shortcut()

    @Slot(int, int, result=str)
    def shortcutFromKey(self, key: int, modifiers: int) -> str:
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
            return ""
        combination = QKeyCombination(Qt.KeyboardModifier(modifiers), Qt.Key(key))
        text = QKeySequence(combination).toString(QKeySequence.PortableText)
        try:
            shortcut_combination(text)
        except ValueError as exc:
            self._set_error(str(exc))
            return ""
        self._set_error("")
        return text

    @Slot(str, result=bool)
    def saveShortcut(self, text: str) -> bool:
        try:
            if text:
                combination = shortcut_combination(text)
                text = QKeySequence(combination).toString(QKeySequence.PortableText)
            self._hotkey.set_shortcut(text)
        except (ValueError, RuntimeError) as exc:
            self._set_error(str(exc))
            return False
        try:
            self._settings.set_shortcut(text)
        except OSError:
            self._restore_shortcut()
            self._set_error("Could not save the shortcut settings.")
            return False
        self._shortcut = text
        self.shortcutChanged.emit()
        self._set_error("")
        return True

    def _restore_shortcut(self) -> None:
        if not self.shortcutSupported:
            self._set_error("Global shortcuts require a Linux X11 session.")
            return
        try:
            self._hotkey.set_shortcut(self._shortcut)
        except (ValueError, RuntimeError) as exc:
            self._set_error(str(exc))

    def _set_error(self, text: str) -> None:
        self._error = text
        self.shortcutErrorChanged.emit()

    def _on_pressed(self) -> None:
        if self._capturing or self._assistant.state != "idle":
            return
        self._assistant.startListening()
        self._held = self._assistant.state == "listening"
        if self._window and not self._window.isVisible():
            self._notify(self._assistant.status)

    def _on_released(self) -> None:
        if self._held:
            self._held = False
            self._assistant.stopListening()
            if self._assistant.state == "idle" and self._window and not self._window.isVisible():
                self._notify(self._assistant.status)

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showWindow()

    def _translate(self) -> None:
        english = self._assistant.language == "en"
        self._open_action.setText("Open T.A.R.S." if english else "Ouvrir T.A.R.S.")
        self._quit_action.setText("Quit" if english else "Quitter")
        self.shortcutErrorChanged.emit()
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        self._tray.setToolTip(f"T.A.R.S. — {self._assistant.status}")

    def _notify(self, message: str) -> None:
        if self._tray_available:
            self._tray.showMessage("T.A.R.S.", message, QSystemTrayIcon.Information, 3000)

    def _refresh_tray(self) -> None:
        available = QSystemTrayIcon.isSystemTrayAvailable()
        if available != self._tray_available:
            self._tray_available = available
            self._tray.setVisible(available)
            self._app.setQuitOnLastWindowClosed(not available)
            self.trayAvailableChanged.emit()
            if not available:
                self.showWindow()

    def shutdown(self) -> None:
        self._tray_timer.stop()
        # Discard a held recording on quit; do not submit a new GLM request.
        self._held = False
        self._hotkey.shutdown()
        self._tray.hide()
        self._menu.deleteLater()
