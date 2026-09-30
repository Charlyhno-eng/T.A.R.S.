from __future__ import annotations

import logging
import multiprocessing
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from core.assistant_controller import AssistantController
from core.desktop_service import DesktopService
from core.paths import data_directory, resource_directory
from core.export_service import ExportService


BASE_DIR = resource_directory() / "src"
UI_DIR = BASE_DIR / "ui"
MAIN_QML = UI_DIR / "Main.qml"


def configure_logging() -> None:
    """Configure application and dependency logging."""
    handlers = []
    if getattr(sys, "frozen", False):
        directory = data_directory() / "logs"
        directory.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(directory / "tars.log", encoding="utf-8"))
        import certifi
        os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
        handlers=handlers,
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
    exporter = ExportService(app)

    engine.rootContext().setContextProperty(
        "assistant",
        assistant,
    )
    engine.rootContext().setContextProperty("desktop", desktop)
    engine.rootContext().setContextProperty("exporter", exporter)

    engine.load(
        QUrl.fromLocalFile(str(MAIN_QML))
    )

    if not engine.rootObjects():
        logging.error(
            "[T.A.R.S.] Impossible de charger Main.qml."
        )

        exporter.shutdown()
        desktop.shutdown()
        assistant.shutdown()

        return -1

    desktop.attach_window(engine.rootObjects()[0])
    QTimer.singleShot(0, assistant.start)
    exit_code = app.exec()

    exporter.shutdown()
    desktop.shutdown()
    assistant.shutdown()

    return exit_code


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--check-bundle" in sys.argv:
        from core.bundle_check import check_bundle
        configure_logging()
        sys.exit(check_bundle(load_models="--check-models" in sys.argv,
                              register_shortcut="--check-shortcut" in sys.argv))
    if len(sys.argv) == 3 and sys.argv[1] == "--export-copy":
        from core.exporter import copy_bundle
        print(f"Export ready: {copy_bundle(Path(sys.argv[2]))}", flush=True)
        sys.exit(0)
    sys.exit(main())
