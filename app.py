from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from core.assistant_controller import AssistantController


BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
MAIN_QML = UI_DIR / "Main.qml"


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )


def main() -> int:
    configure_logging()

    app = QGuiApplication(sys.argv)

    app.setApplicationName("T.A.R.S.")
    app.setOrganizationName("T.A.R.S.")

    engine = QQmlApplicationEngine()

    # Permet à Main.qml et aux composants de faire :
    # import theme 1.0
    engine.addImportPath(str(UI_DIR))

    # ------------------------------------------------------------------
    # Couche métier
    # ------------------------------------------------------------------

    assistant = AssistantController()

    # Expose le contrôleur à QML sous le nom "assistant".
    #
    # QML peut maintenant utiliser :
    #
    # assistant.state
    # assistant.status
    # assistant.ttsReady
    # assistant.ttsLoading
    # assistant.audioPath
    # assistant.activate()
    #
    engine.rootContext().setContextProperty(
        "assistant",
        assistant,
    )

    # ------------------------------------------------------------------
    # Chargement de l'interface
    # ------------------------------------------------------------------

    engine.load(
        QUrl.fromLocalFile(str(MAIN_QML))
    )

    if not engine.rootObjects():
        logging.error(
            "[T.A.R.S.] Impossible de charger Main.qml."
        )

        assistant.shutdown()

        return -1

    # ------------------------------------------------------------------
    # Arrêt propre
    # ------------------------------------------------------------------

    exit_code = app.exec()

    assistant.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
