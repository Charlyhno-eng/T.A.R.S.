"""Install a Linux bundle and its application-menu entry for the current user."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import tempfile


EXPORT_NAME = re.compile(r"TARS-linux-[\w-]+-\d{8}-\d{6}-\d{6}\Z")


def linux_exports(dist: Path) -> list[Path]:
    return sorted(path for path in dist.glob("TARS-linux-*")
                  if EXPORT_NAME.fullmatch(path.name) and path.is_dir() and not path.is_symlink())


def validate_bundle(bundle: Path) -> None:
    if not (bundle / "TARS").is_file() or not os.access(bundle / "TARS", os.X_OK):
        raise ValueError(f"Missing executable Linux bundle: {bundle}")
    if not (bundle / "_internal" / "assets" / "tars-mascot.png").is_file():
        raise ValueError(f"Missing bundled application icon: {bundle}")


def desktop_entry(installation: Path) -> str:
    # Desktop Exec has its own quoting rules, including a second backslash
    # decoding pass and percent field codes. No shell is involved.
    executable = str(installation / "TARS").replace("%", "%%")
    for character in ("\\", '"', "`", "$"):
        executable = executable.replace(character, "\\" + character)
    executable = executable.replace("\\", "\\\\")
    icon = str(installation / "_internal" / "assets" / "tars-mascot.png").replace("\\", "\\\\")
    if any(character in str(installation) for character in "\n\r"):
        raise ValueError("Installation paths cannot contain newlines.")
    return ("[Desktop Entry]\nType=Application\nName=T.A.R.S.\n"
            "Comment=Personal voice assistant\n"
            f'Exec="{executable}"\nIcon={icon}\n'
            "Terminal=false\nCategories=Utility;\nKeywords=TARS;assistant;voice;\n")


def install_bundle(bundle: Path, installation: Path, applications: Path) -> Path:
    """Move the complete bundle; restore the previous installation on failure."""
    bundle = bundle.expanduser().resolve()
    installation = installation.expanduser().absolute()
    validate_bundle(bundle)
    if installation.is_symlink() or installation.resolve().is_relative_to(bundle) or bundle.is_relative_to(installation.resolve()):
        raise ValueError("The installation must be outside the source bundle and cannot be a symlink.")
    entry = desktop_entry(installation)
    installation.parent.mkdir(parents=True, exist_ok=True)
    applications.mkdir(parents=True, exist_ok=True)
    launcher = applications / "tars.desktop"
    with tempfile.TemporaryDirectory(prefix=".tars-install-", dir=installation.parent) as temporary:
        backup = Path(temporary) / "previous"
        if installation.exists():
            shutil.move(str(installation), str(backup))
        moved = False
        try:
            shutil.move(str(bundle), str(installation))
            moved = True
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=applications,
                                             prefix=".tars-", delete=False) as file:
                pending = Path(file.name)
                file.write(entry)
            try:
                pending.chmod(0o644)
                pending.replace(launcher)
            finally:
                pending.unlink(missing_ok=True)
        except Exception:
            if moved:
                shutil.move(str(installation), str(bundle))
            if backup.exists():
                shutil.move(str(backup), str(installation))
            raise
    return launcher


def clean_linux_exports(dist: Path) -> None:
    """Remove generated Linux exports only, preserving unrelated dist contents."""
    for export in linux_exports(dist):
        children = list(export.iterdir())
        if not children:
            export.rmdir()
        elif len(children) == 1 and children[0].name == "TARS" and not children[0].is_symlink():
            validate_bundle(children[0])
            shutil.rmtree(export)
