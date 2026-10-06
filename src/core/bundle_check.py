"""Exercise packaged resources and dynamic voice imports without recording."""
from __future__ import annotations

from pathlib import Path
import tempfile
import threading

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
from providers.tts.adapter import TTSAdapter


def _check_synthesis(provider: TTSAdapter | PocketTTSProvider, language: str,
                     output: Path) -> None:
    """Exercise streaming inference and produce recorder-format audio for STT."""
    import numpy as np
    from scipy.io import wavfile
    from scipy.signal import resample_poly
    from math import gcd

    text = "Hello, this is TARS." if language == "en" else "Bonjour, je suis TARS."
    name = type(provider).__name__
    chunks = list(provider.generate_stream(text, threading.Event()))
    if not chunks:
        raise RuntimeError(f"{name} {language} produced no audio.")
    rate = chunks[0][1]
    if rate <= 0 or any(chunk_rate != rate for _, chunk_rate in chunks):
        raise RuntimeError(f"{name} {language} produced inconsistent sample rates.")
    audio = np.frombuffer(b"".join(chunk for chunk, _ in chunks), dtype=np.float32)
    if not audio.size or not np.isfinite(audio).all() or not np.any(audio):
        raise RuntimeError(f"{name} {language} produced invalid audio.")
    divisor = gcd(rate, 16_000)
    audio = resample_poly(audio, 16_000 // divisor, rate // divisor)
    wavfile.write(output, 16_000, (np.clip(audio, -1, 1) * 32767).astype(np.int16))
    print(f"{name} {language}: streaming synthesis passed", flush=True)


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
    audio_directory = tempfile.TemporaryDirectory(prefix="tars-bundle-check-")
    audio_files = []
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
        if not callable(TTSModel.load_model):
            raise RuntimeError("Pocket TTS does not expose its model loader.")
        from piper import PiperVoice
        if not callable(PiperVoice.load):
            raise RuntimeError("Piper TTS does not expose its model loader.")
        ParakeetProvider._import_nemo()
        for language in ("en", "fr"):
            for provider_type in (TTSAdapter, PocketTTSProvider):
                provider = provider_type(language=language)
                name = provider_type.__name__
                if load_models and provider.installed:
                    provider.load(language)
                    audio_path = Path(audio_directory.name) / f"{name}-{language}.wav"
                    _check_synthesis(provider, language, audio_path)
                    audio_files.append((language, audio_path))
                    provider.shutdown()
                    print(f"{name} {language}: loaded", flush=True)
                elif load_models:
                    if provider_type is TTSAdapter:
                        raise RuntimeError(f"Piper TTS {language} is not installed; download both voices before checking their loading.")
                    print(f"{name} {language}: not installed", flush=True)
        if load_models:
            provider = ParakeetProvider()
            if not provider.installed:
                raise RuntimeError("Parakeet is not installed; download models before checking their loading.")
            provider.load()
            for language, audio_path in audio_files:
                text = provider.transcribe(audio_path, language)
                if not text:
                    raise RuntimeError(f"Parakeet {language} produced an empty transcription.")
                print(f"Parakeet {language}: transcription passed ({text})", flush=True)
            provider.shutdown()
            print("Parakeet: loaded", flush=True)
        if errors:
            raise RuntimeError(f"QML errors: {errors}")
        print("Bundle check passed: QML, mascot, STT/TTS imports and language providers.", flush=True)
        return 0
    finally:
        audio_directory.cleanup()
        engine.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        exporter.shutdown()
        desktop.shutdown()
        assistant.shutdown()
