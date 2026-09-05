from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from PySide6.QtCore import (
    QObject,
    QThread,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtQml import QQmlApplicationEngine


BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
MAIN_QML = UI_DIR / "Main.qml"

TTS_PROVIDER_PATH = (
    BASE_DIR
    / "providers"
    / "tts"
    / "pocket-tts.py"
)


class TTSWorker(QObject):
    """
    Worker exécuté dans un thread séparé.

    La génération Pocket TTS peut être coûteuse.
    Elle ne doit donc pas bloquer le thread graphique Qt.
    """

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, provider) -> None:
        super().__init__()

        self.provider = provider

    @Slot(str)
    def generate(self, text: str) -> None:
        try:
            output_path = self.provider.speak(text)
            self.finished.emit(str(output_path))

        except Exception as exc:
            self.error.emit(str(exc))


class TTSController(QObject):
    """
    Contrôleur Qt exposé à QML.

    QML appelle :
        ttsController.speak("...")

    Le contrôleur :
        1. lance la génération dans un thread ;
        2. récupère le WAV ;
        3. lance sa lecture avec QtMultimedia.
    """

    speakingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self._provider = self._load_provider()

        self._thread = QThread()
        self._worker = TTSWorker(self._provider)

        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._thread_started)

        self._worker.finished.connect(self._on_audio_generated)
        self._worker.error.connect(self._on_error)

        self._thread.start()

        self._audio_output = QAudioOutput()
        self._audio_output.setVolume(1.0)

        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        self._player.playbackStateChanged.connect(
            self._on_playback_state_changed
        )

        self._speaking = False

    def _load_provider(self):
        """
        Charge providers/tts/pocket-tts.py malgré le tiret
        présent dans son nom de fichier.
        """

        if not TTS_PROVIDER_PATH.exists():
            raise FileNotFoundError(
                f"Provider TTS introuvable : {TTS_PROVIDER_PATH}"
            )

        spec = importlib.util.spec_from_file_location(
            "tars_pocket_tts",
            TTS_PROVIDER_PATH,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                "Impossible de charger le provider Pocket TTS."
            )

        module = importlib.util.module_from_spec(spec)

        # Le provider utilise un import relatif vers adapter.py.
        # On charge donc le package parent comme un vrai package.
        package_dir = TTS_PROVIDER_PATH.parent

        package_name = "tars_tts_provider"

        if package_name not in sys.modules:
            import types

            package = types.ModuleType(package_name)
            package.__path__ = [str(package_dir)]
            sys.modules[package_name] = package

        spec = importlib.util.spec_from_file_location(
            f"{package_name}.pocket_tts",
            TTS_PROVIDER_PATH,
        )

        if spec is None or spec.loader is None:
            raise ImportError(
                "Impossible de créer le module Pocket TTS."
            )

        module = importlib.util.module_from_spec(spec)

        module.__package__ = package_name

        sys.modules[f"{package_name}.pocket_tts"] = module

        spec.loader.exec_module(module)

        return module.PocketTTSProvider()

    def _thread_started(self) -> None:
        pass

    @Slot(str)
    def speak(self, text: str) -> None:
        """
        Demande une génération vocale.
        """

        if not text or not text.strip():
            return

        if self._speaking:
            return

        self._set_speaking(True)

        # On appelle directement la méthode du worker.
        # Le signal est connecté via QueuedConnection grâce
        # au changement de thread de l'objet worker.
        QMetaObject.invokeMethod(
            self._worker,
            "generate",
            Qt.QueuedConnection,
            Q_ARG(str, text),
        )

    def _on_audio_generated(self, audio_path: str) -> None:
        """
        Appelé lorsque Pocket TTS a terminé la génération.
        """

        path = Path(audio_path)

        if not path.exists():
            self._on_error(
                f"Le fichier audio n'existe pas : {path}"
            )
            return

        self._player.setSource(
            QUrl.fromLocalFile(str(path))
        )

        self._player.play()

    def _on_playback_state_changed(self, state) -> None:
        """
        Met à jour l'état speaking pendant la lecture.
        """

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._set_speaking(True)

        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self._set_speaking(False)

        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._set_speaking(False)

    def _on_error(self, message: str) -> None:
        print(f"[T.A.R.S.][TTS][ERREUR] {message}")

        self._set_speaking(False)
        self.errorOccurred.emit(message)

    def _set_speaking(self, value: bool) -> None:
        if self._speaking == value:
            return

        self._speaking = value
        self.speakingChanged.emit(value)

    def shutdown(self) -> None:
        """
        Arrête proprement le TTS.
        """

        self._player.stop()

        self._provider.close()

        self._thread.quit()
        self._thread.wait()


# Imports Qt nécessaires à QMetaObject.invokeMethod.
from PySide6.QtCore import (
    Q_ARG,
    QMetaObject,
    Qt,
)


def main() -> int:
    app = QGuiApplication(sys.argv)

    app.setApplicationName("T.A.R.S.")
    app.setOrganizationName("T.A.R.S.")

    engine = QQmlApplicationEngine()

    engine.addImportPath(str(UI_DIR))

    # Contrôleur TTS exposé à QML.
    tts_controller = TTSController()

    engine.rootContext().setContextProperty(
        "ttsController",
        tts_controller,
    )

    engine.load(
        QUrl.fromLocalFile(str(MAIN_QML))
    )

    if not engine.rootObjects():
        tts_controller.shutdown()
        return -1

    exit_code = app.exec()

    tts_controller.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
