import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
datas = [(str(root / "src" / "ui"), "src/ui"),
         (str(root / "assets" / "tars-mascot.png"), "assets"),
         (str(root / "src" / "providers" / "tts" / "fr-tom-medium"),
          "src/providers/tts/fr-tom-medium")]
hiddenimports = ["PySide6.QtQuick", "PySide6.QtMultimedia", "scipy.io.wavfile"]
hiddenimports += collect_submodules("piper", filter=lambda name: not name.startswith("piper.train"),
                                   on_error="warn once")
for package in ("pocket_tts", "nemo.collections.asr", "nemo.core", "nemo.utils"):
    hiddenimports += collect_submodules(package, on_error="warn once")
if sys.platform != "darwin":
    # Cython imports these extension modules without Python import statements.
    hiddenimports += collect_submodules("cuda.bindings", on_error="warn once")
    hiddenimports += collect_submodules("cuda.pathfinder", on_error="warn once")
    datas += collect_data_files("cuda.pathfinder")
for package in ("piper", "pocket_tts", "nemo", "hydra", "omegaconf"):
    datas += collect_data_files(package, include_py_files=True)
for distribution in ("nemo_toolkit", "pocket-tts", "piper-tts"):
    datas += copy_metadata(distribution, recursive=True)
for package in ("lightning", "lightning_fabric", "pytorch_lightning"):
    datas += collect_data_files(package)

analysis = Analysis(
    [str(root / "src" / "app.py")], pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("piper"), datas=datas, hiddenimports=hiddenimports,
    hookspath=[str(root / "packaging" / "hooks")],
    excludes=["PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "pytest"],
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
)
# PyTorch wheels also contain native framework self-tests. Keep the runtime
# tools (especially torch_shm_manager), but omit those test executables/data.
def runtime_payload(entry):
    path = Path(entry[0])
    return not (path.parts[:2] == ("torch", "test") or
                (path.parts[:2] == ("torch", "bin") and
                 (path.name.startswith("test_") or path.name.endswith("Test"))))

analysis.binaries = [entry for entry in analysis.binaries if runtime_payload(entry)]
analysis.datas = [entry for entry in analysis.datas if runtime_payload(entry)]
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, [], exclude_binaries=True, name="TARS",
          console=sys.platform.startswith("linux"), upx=False,
          strip=sys.platform.startswith("linux"),
          icon=str(root / "assets" / "tars-mascot.png") if sys.platform == "win32" else None)
bundle = COLLECT(exe, analysis.binaries, analysis.datas, name="TARS", upx=False,
                 strip=sys.platform.startswith("linux"))
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
