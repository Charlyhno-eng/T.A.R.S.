"""Keep upstream native-library handling without force-importing all of torch.

Ordinary Python dependencies are followed by Analysis. Native extension
namespaces and registered compiler polyfills need explicit dynamic imports.
"""
from pathlib import Path
import runpy

import _pyinstaller_hooks_contrib
from PyInstaller.utils.hooks import collect_submodules

upstream = runpy.run_path(
    str(Path(_pyinstaller_hooks_contrib.__file__).parent / "stdhooks" / "hook-torch.py")
)
datas = upstream.get("datas", [])
binaries = upstream.get("binaries", [])
module_collection_mode = upstream.get("module_collection_mode", "pyz+py")
bindepend_symlink_suppression = upstream.get("bindepend_symlink_suppression", [])
warn_on_missing_hiddenimports = False
hiddenimports = [
    name for name in upstream.get("hiddenimports", [])
    if not name.startswith("torch.") or name.startswith("torch._C.")
]
# torch.compiler.disable (used by Pocket TTS) loads these by string name.
hiddenimports += collect_submodules("torch._dynamo.polyfills")
