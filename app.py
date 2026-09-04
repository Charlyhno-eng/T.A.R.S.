import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

BASE_DIR = Path(__file__).resolve().parent
UI_DIR = BASE_DIR / "ui"
MAIN_QML = UI_DIR / "Main.qml"


def main() -> int:
    app = QGuiApplication(sys.argv)
    app.setApplicationName("T.A.R.S.")
    app.setOrganizationName("T.A.R.S.")

    engine = QQmlApplicationEngine()

    # Permet à Main.qml et aux composants de faire `import theme 1.0`
    engine.addImportPath(str(UI_DIR))

    engine.load(QUrl.fromLocalFile(str(MAIN_QML)))

    if not engine.rootObjects():
        # Le chargement du QML a échoué (erreur affichée dans la console)
        return -1

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
