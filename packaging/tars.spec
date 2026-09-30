import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / "src" / "ui"), "src/ui"),
         (str(root / "assets" / "tars-mascot.png"), "assets")]
hiddenimports = ["PySide6.QtQuick", "PySide6.QtMultimedia", "scipy.io.wavfile"]
for package in ("pocket_tts", "nemo.collections.asr", "nemo.core", "nemo.utils"):
    hiddenimports += collect_submodules(package, on_error="warn once")
if sys.platform != "darwin":
    # Cython imports these extension modules without Python import statements.
    hiddenimports += collect_submodules("cuda.bindings", on_error="warn once")
    hiddenimports += collect_submodules("cuda.pathfinder", on_error="warn once")
    datas += collect_data_files("cuda.pathfinder")
for package in ("pocket_tts", "nemo", "hydra", "omegaconf"):
    datas += collect_data_files(package, include_py_files=True)
for distribution in ("nemo_toolkit", "pocket-tts"):
    datas += copy_metadata(distribution, recursive=True)
for package in ("lightning", "lightning_fabric", "pytorch_lightning"):
    datas += collect_data_files(package)

analysis = Analysis(
    [str(root / "src" / "app.py")], pathex=[str(root / "src")],
    binaries=[], datas=datas, hiddenimports=hiddenimports,
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "pytest"],
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
)
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="TARS",
          console=sys.platform.startswith("linux"), upx=False,
          icon=str(root / "assets" / "tars-mascot.png") if sys.platform == "win32" else None)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="TARS", upx=False)
if sys.platform == "darwin":
    from PIL import Image
    icon = root / "build" / "macos" / "tars.icns"
    icon.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(root / "assets" / "tars-mascot.png") as mascot:
        mascot.save(icon, format="ICNS")
    app = BUNDLE(bundle, name="TARS.app", bundle_identifier="computer.tars.assistant",
                 icon=str(icon),
                 info_plist={"NSMicrophoneUsageDescription": "TARS records your voice while you hold your shortcut.",
                             "NSHighResolutionCapable": True})
