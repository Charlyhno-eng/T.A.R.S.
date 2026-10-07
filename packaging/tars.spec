import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
sys.path.insert(0, str(root / "packaging"))
from runtime_dependencies import HIDDEN_IMPORTS, EXCLUDED_MODULES, DATA_FILES, runtime_payload
datas = [(str(root / "src" / "ui"), "src/ui"),
         (str(root / "assets" / "tars-mascot.png"), "assets")]
hiddenimports = list(HIDDEN_IMPORTS)
# Hydra discovers built-in plugins at runtime rather than through imports.
hiddenimports += collect_submodules("hydra._internal.core_plugins")
for package, includes in DATA_FILES.items():
    datas += collect_data_files(package, includes=includes)
for distribution in ("nemo_toolkit", "pocket-tts", "piper-tts"):
    datas += copy_metadata(distribution, recursive=True)
for package in ("lightning", "lightning_fabric", "pytorch_lightning"):
    datas += collect_data_files(package)

analysis = Analysis(
    [str(root / "src" / "app.py")], pathex=[str(root / "src")],
    binaries=collect_dynamic_libs("piper"), datas=datas, hiddenimports=hiddenimports,
    hookspath=[str(root / "packaging" / "hooks")],
    excludes=list(EXCLUDED_MODULES),
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
)
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
