from __future__ import annotations

from datetime import datetime
from pathlib import Path
import platform
import shutil
import sys


def host_platform() -> str:
    return {"linux": "linux", "win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)


def new_export_directory(destination: Path, target: str) -> Path:
    """Create a new destination without overwriting an earlier export."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    directory = destination.expanduser().resolve() / f"TARS-{target}-{platform.machine()}-{stamp}"
    directory.mkdir(parents=True)
    return directory


def copy_bundle(destination: Path) -> Path:
    """Export an already frozen application without needing a build toolchain."""
    executable = Path(sys.executable).resolve()
    source = executable.parents[2] if sys.platform == "darwin" else executable.parent
    if destination.expanduser().resolve().is_relative_to(source):
        raise ValueError("Choose a destination outside the application folder.")
    output = new_export_directory(destination, host_platform()) / source.name
    shutil.copytree(source, output, symlinks=True)
    return output
