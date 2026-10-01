"""Keep Qt's recursive QML imports without collecting unrelated Qt modules."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess


def scan_modules(scanner: Path, ui: Path, qml: Path) -> set[Path]:
    result = subprocess.run(
        [str(scanner), "-rootPath", str(ui), "-importPath", str(ui),
         "-importPath", str(qml)],
        check=True, capture_output=True, text=True,
    )
    modules = set()
    for entry in json.loads(result.stdout):
        if entry.get("type") != "module":
            continue
        # QML is a built-in module with no filesystem resources.
        if not entry.get("path"):
            if entry.get("name") != "QML":
                raise RuntimeError(f"Unresolved QML import: {entry.get('name')}")
            continue
        path = Path(entry["path"]).resolve()
        if path.is_relative_to(qml.resolve()):
            modules.add(path)
    if not modules:
        raise RuntimeError("Qt's QML scanner did not find any Qt modules.")
    return modules


def select_files(files: list[tuple[str, str]], qml: Path,
                 modules: set[Path]) -> list[tuple[str, str]]:
    """Select by owning qmldir, so retaining QtQuick does not keep all children."""
    qml = qml.resolve()
    selected = []
    for source, destination in files:
        path = Path(source).resolve()
        owner = path if path.is_dir() else path.parent
        while owner.is_relative_to(qml):
            if (owner / "qmldir").is_file():
                if owner in modules:
                    selected.append((source, destination))
                break
            owner = owner.parent
    return selected
