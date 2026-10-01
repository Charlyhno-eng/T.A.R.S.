from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
from qml_dependencies import scan_modules, select_files
sys.path.pop(0)


class QMLPackagingTests(unittest.TestCase):
    def test_keeps_imported_modules_and_assets_without_unrelated_children(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            qml = Path(directory)
            quick = qml / "QtQuick"
            controls = quick / "Controls"
            unused = quick / "Scene3D"
            for module in (quick, controls, unused):
                module.mkdir(parents=True)
                (module / "qmldir").touch()
            assets = controls / "images"
            assets.mkdir()
            files = [(str(quick / "plugin.so"), "QtQuick"),
                     (str(controls / "Button.qml"), "QtQuick/Controls"),
                     (str(assets), "QtQuick/Controls/images"),
                     (str(unused / "plugin.so"), "QtQuick/Scene3D")]
            self.assertEqual(select_files(files, qml, {quick, controls}), files[:3])

    def test_unresolved_imports_fail_the_build(self) -> None:
        result = subprocess.CompletedProcess([], 0, json.dumps([
            {"type": "module", "name": "QtQuick.Missing"}
        ]))
        with patch("qml_dependencies.subprocess.run", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Unresolved QML import"):
                scan_modules(Path("scanner"), ROOT / "src/ui", Path("qml"))

    def test_scanner_failures_are_not_silently_ignored(self) -> None:
        with patch("qml_dependencies.subprocess.run",
                   side_effect=subprocess.CalledProcessError(1, "scanner")):
            with self.assertRaises(subprocess.CalledProcessError):
                scan_modules(Path("scanner"), ROOT / "src/ui", Path("qml"))

    def test_real_interface_keeps_controls_styles_and_recursive_dependencies(self) -> None:
        from PySide6.QtCore import QLibraryInfo
        qml = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
        name = "qmlimportscanner.exe" if sys.platform == "win32" else "qmlimportscanner"
        scanner = next((Path(QLibraryInfo.path(kind)) / name
                        for kind in (QLibraryInfo.LibraryPath.LibraryExecutablesPath,
                                     QLibraryInfo.LibraryPath.BinariesPath)
                        if (Path(QLibraryInfo.path(kind)) / name).is_file()), None)
        if scanner is None:
            self.skipTest("Qt's QML scanner is not installed")
        modules = scan_modules(scanner, ROOT / "src/ui", qml)
        for relative in ("QtQuick", "QtQml/Models", "QtQuick/Controls",
                         "QtQuick/Templates", "QtQuick/Layouts", "QtQuick/Controls/Basic"):
            self.assertIn((qml / relative).resolve(), modules)
        self.assertNotIn((qml / "QtQuick3D").resolve(), modules)
        self.assertNotIn((qml / "QtWebEngine").resolve(), modules)
        for style in (qml / "QtQuick/Controls").iterdir():
            if (style / "qmldir").is_file() and style.name != "designer":
                self.assertIn(style.resolve(), modules)


if __name__ == "__main__":
    unittest.main()
