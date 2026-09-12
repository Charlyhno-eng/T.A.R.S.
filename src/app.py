from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
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
    library_loggers = (
        "httpx",
        "huggingface_hub",
        "nv_one_logger",
        "pocket_tts",
    )
    for logger_name in library_loggers:
        logging.getLogger(logger_name).setLevel(logging.ERROR)


def main() -> int:
    configure_logging()

    app = QGuiApplication(sys.argv)

    app.setApplicationName("T.A.R.S.")
    app.setOrganizationName("T.A.R.S.")

    engine = QQmlApplicationEngine()

    engine.addImportPath(str(UI_DIR))

    assistant = AssistantController()

    engine.rootContext().setContextProperty(
        "assistant",
        assistant,
    )

    engine.load(
        QUrl.fromLocalFile(str(MAIN_QML))
    )

    if not engine.rootObjects():
        logging.error(
            "[T.A.R.S.] Impossible de charger Main.qml."
        )

        assistant.shutdown()

        return -1

    QTimer.singleShot(0, assistant.start)
    exit_code = app.exec()

    assistant.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
