from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from core.assistant_controller import AssistantController
from core.desktop_service import DesktopService


BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
MAIN_QML = UI_DIR / "Main.qml"


def configure_logging() -> None:
    """Configure application and dependency logging."""
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
    """Launch the Qt application and return its exit code."""
    configure_logging()

    app = QApplication(sys.argv)

    app.setApplicationName("T.A.R.S.")
    app.setOrganizationName("T.A.R.S.")
    icon_path = BASE_DIR.parent / "assets" / "tars-mascot.png"
    app.setWindowIcon(QIcon(str(icon_path)))

    engine = QQmlApplicationEngine()

    engine.addImportPath(str(UI_DIR))

    assistant = AssistantController()
    desktop = DesktopService(app, assistant, icon_path)

    engine.rootContext().setContextProperty(
        "assistant",
        assistant,
    )
    engine.rootContext().setContextProperty("desktop", desktop)

    engine.load(
        QUrl.fromLocalFile(str(MAIN_QML))
    )

    if not engine.rootObjects():
        logging.error(
            "[T.A.R.S.] Impossible de charger Main.qml."
        )

        desktop.shutdown()
        assistant.shutdown()

        return -1

    desktop.attach_window(engine.rootObjects()[0])
    QTimer.singleShot(0, assistant.start)
    exit_code = app.exec()

    desktop.shutdown()
    assistant.shutdown()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
