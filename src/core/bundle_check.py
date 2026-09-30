"""Exercise packaged resources and dynamic voice imports without recording."""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEvent, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from core.assistant_controller import AssistantController
from core.desktop_service import DesktopService
from core.export_service import ExportService
from core.global_shortcut import GlobalShortcut
from core.paths import resource_directory
from providers.stt.parakeet import ParakeetProvider
from providers.tts.pocket_tts import PocketTTSProvider


def check_bundle(load_models: bool = False, register_shortcut: bool = False) -> int:
    app = QApplication([])
    resources = resource_directory()
    assistant = AssistantController()
    desktop = DesktopService(app, assistant, resources / "assets" / "tars-mascot.png")
    exporter = ExportService(app)
    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"visible": False})
    engine.addImportPath(str(resources / "src" / "ui"))
    for name, value in (("assistant", assistant), ("desktop", desktop), ("exporter", exporter)):
        engine.rootContext().setContextProperty(name, value)
    errors = []
    engine.warnings.connect(lambda warnings: errors.extend(str(error) for error in warnings))
    try:
        engine.load(QUrl.fromLocalFile(str(resources / "src" / "ui" / "Main.qml")))
        if not engine.rootObjects() or errors:
            raise RuntimeError(f"QML load failed: {errors}")
        desktop.attach_window(engine.rootObjects()[0])
        if not (resources / "assets" / "tars-mascot.png").is_file():
            raise RuntimeError("The tray mascot is missing from the bundle.")
        app.processEvents()
        if register_shortcut:
            shortcut = GlobalShortcut()
            conflicting = GlobalShortcut()
            try:
                shortcut.set_shortcut("Ctrl+Alt+Shift+F8")
                try:
                    conflicting.set_shortcut("Ctrl+Alt+Shift+F8")
                except RuntimeError as exc:
                    if "already used" not in str(exc):
                        raise
                else:
                    raise RuntimeError("Shortcut conflicts were not detected.")
                shortcut.shutdown()
                conflicting.set_shortcut("Ctrl+Alt+Shift+F8")
                print("Global shortcut: registration, conflict and release passed", flush=True)
            finally:
                shortcut.shutdown()
                conflicting.shutdown()
        from pocket_tts import TTSModel
        ParakeetProvider._import_nemo()
        for language in ("en", "fr"):
            provider = PocketTTSProvider(language=language)
            if load_models and provider.installed:
                provider.load(language)
                provider.shutdown()
                print(f"Pocket TTS {language}: loaded", flush=True)
            elif load_models:
                print(f"Pocket TTS {language}: not installed", flush=True)
        if load_models:
            provider = ParakeetProvider()
            if not provider.installed:
                raise RuntimeError("Parakeet is not installed; download models before checking their loading.")
            provider.load()
            provider.shutdown()
            print("Parakeet: loaded", flush=True)
        if errors:
            raise RuntimeError(f"QML errors: {errors}")
        print("Bundle check passed: QML, mascot, STT/TTS imports and language providers.", flush=True)
        return 0
    finally:
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        exporter.shutdown()
        desktop.shutdown()
        assistant.shutdown()
