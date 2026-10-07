from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packaging"))
from qml_dependencies import scan_modules, select_files
from runtime_dependencies import DATA_FILES, arrow_runtime_binary, arrow_runtime_module, runtime_payload
sys.path.pop(0)


class RuntimePackagingTests(unittest.TestCase):
    def test_arrow_hook_filters_versioned_flight_libraries_from_data_as_well_as_binaries(self) -> None:
        flight = ("/pyarrow/libarrow_flight.so.2500", "pyarrow")
        required = ("/pyarrow/libarrow_substrait.so.2500", "pyarrow")
        metadata = ("/pyarrow/metadata.json", "pyarrow")
        hooks = SimpleNamespace(
            collect_data_files=Mock(return_value=[flight, required, metadata]),
            collect_dynamic_libs=Mock(return_value=[flight, required]),
            collect_submodules=Mock(return_value=["pyarrow.lib"]),
        )
        spec = importlib.util.spec_from_file_location(
            "test_tars_arrow_hook", ROOT / "packaging/hooks/hook-pyarrow.py")
        hook = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"PyInstaller.utils.hooks": hooks}):
            spec.loader.exec_module(hook)
        self.assertEqual(hook.binaries, [required])
        self.assertEqual(hook.datas, [required, metadata])

    def test_arrow_keeps_dataset_dependencies_without_unused_server_libraries(self) -> None:
        for name in ("pyarrow.flight", "pyarrow._flight", "pyarrow.substrait", "pyarrow.tests.test_array",
                     "pyarrow.libarrow_python_flight", "pyarrow._pyarrow_cpp_tests"):
            self.assertFalse(arrow_runtime_module(name))
        for name in ("pyarrow.lib", "pyarrow.dataset", "pyarrow._dataset", "pyarrow.parquet"):
            self.assertTrue(arrow_runtime_module(name))
        for name in ("libarrow_flight.so.2500", "arrow_python_flight.dll"):
            self.assertFalse(arrow_runtime_binary(name))
        for name in ("libarrow.so.2500", "arrow_python.dll", "libparquet.so.2500", "libarrow_substrait.dylib"):
            self.assertTrue(arrow_runtime_binary(name))

    def test_torch_hook_preserves_native_dependencies_without_collecting_all_python_modules(self) -> None:
        upstream = {
            "datas": [("/torch/data", "torch")],
            "binaries": [("/mkl.dll", ".")],
            "module_collection_mode": "pyz+py",
            "bindepend_symlink_suppression": ["**/torch/lib/*.so*"],
            "hiddenimports": ["torch.nn", "torch._C._fft", "torch.testing._internal",
                              "torch._dynamo.polyfills.copy", "nvidia.cublas"],
        }
        spec = importlib.util.spec_from_file_location(
            "test_tars_torch_hook", ROOT / "packaging/hooks/hook-torch.py")
        hook = importlib.util.module_from_spec(spec)
        collect = Mock(return_value=["torch._dynamo.polyfills.copy"])
        with patch("runpy.run_path", return_value=upstream), patch.dict(sys.modules, {
            "_pyinstaller_hooks_contrib": SimpleNamespace(__file__="/hooks/__init__.py"),
            "PyInstaller.utils.hooks": SimpleNamespace(collect_submodules=collect),
        }):
            spec.loader.exec_module(hook)
        self.assertEqual(hook.hiddenimports, ["torch._C._fft", "nvidia.cublas", "torch._dynamo.polyfills.copy"])
        collect.assert_called_once_with("torch._dynamo.polyfills")
        self.assertEqual(hook.binaries, upstream["binaries"])
        self.assertEqual(hook.datas, upstream["datas"])
        self.assertEqual(hook.module_collection_mode, "pyz+py")
        self.assertEqual(hook.bindepend_symlink_suppression,
                         upstream["bindepend_symlink_suppression"])

    def test_retains_runtime_tools_and_removes_native_framework_tests(self) -> None:
        for name in ("torch/test/basic", "torch/bin/test_api", "torch\\bin\\TensorTest",
                     "pyarrow/libarrow_flight.so.2500", "libarrow_flight.so.2500",
                     "pyarrow/_pyarrow_cpp_tests.so"):
            self.assertFalse(runtime_payload((name, "/source", "BINARY")))
        for name in ("torch/bin/torch_shm_manager", "torch/lib/libtorch_cpu.so",
                     "piper/espeakbridge.pyd"):
            self.assertTrue(runtime_payload((name, "/source", "BINARY")))

    def test_resource_selection_preserves_voice_data_without_sources_or_web_assets(self) -> None:
        try:
            from PyInstaller.utils.hooks import collect_data_files
        except ImportError:
            self.skipTest("Install the build dependency group to check collected resources")
        from providers.tts.pocket_tts import PocketTTSProvider

        selected = {}
        for package, includes in DATA_FILES.items():
            selected[package] = collect_data_files(package, includes=includes)
            self.assertTrue(selected[package], package)
            self.assertFalse(any(Path(source).suffix == ".py"
                                 for source, _ in selected[package]))
        piper_sources = [Path(source) for source, _ in selected["piper"]]
        self.assertTrue(any(path.name == "en_dict" for path in piper_sources))
        self.assertTrue(any(path.name == "fr_dict" for path in piper_sources))
        self.assertFalse(any("templates" in path.parts for path in piper_sources))
        pocket_configs = {Path(source).stem for source, _ in selected["pocket_tts"]}
        self.assertEqual(pocket_configs, {info["pocket_language"]
                                        for info in PocketTTSProvider.LANGUAGES.values()})


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
