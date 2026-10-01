"""Use Qt's import scanner before PyInstaller follows plugin library dependencies."""
from pathlib import Path
import sys

from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

packaging = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(packaging))
from qml_dependencies import scan_modules, select_files

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
locations = pyside6_library_info.location
qml = Path(locations["QmlImportsPath"])
scanner_name = "qmlimportscanner.exe" if sys.platform == "win32" else "qmlimportscanner"
scanner = next((Path(locations[key]) / scanner_name
                for key in ("LibraryExecutablesPath", "BinariesPath")
                if (Path(locations[key]) / scanner_name).is_file()), None)
if scanner is None:
    raise RuntimeError("Qt's qmlimportscanner is required to build the application.")
modules = scan_modules(scanner, packaging.parent / "src" / "ui", qml)
# Keep upstream handling of plugin binaries, resource folders, and platform layout.
qml_binaries, qml_datas = pyside6_library_info.collect_qtqml_files()
binaries += select_files(qml_binaries, qml, modules)
datas += select_files(qml_datas, qml, modules)
