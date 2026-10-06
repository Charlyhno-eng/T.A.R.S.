"""Build on the target OS: uv run --group build python scripts/build_app.py."""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from core.exporter import host_platform, new_export_directory
from core.settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Export TARS with Python, Qt and voice engines included.")
    parser.add_argument("--platform", choices=["linux", "windows", "macos"], default=host_platform())
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if args.platform != host_platform():
        parser.error(f"Build {args.platform} on that OS; this machine builds {host_platform()}.")
    if importlib.util.find_spec("PyInstaller") is None:
        parser.error("Install build tools first: uv sync --group build")
    import torch
    if torch.version.cuda is not None or torch.version.hip is not None:
        parser.error("The export requires CPU-only PyTorch. Run uv sync --group build first.")
    # Preserve this user's checkout preferences for the exported application.
    # They are migrated to the writable user folder, never into the bundle.
    Settings()
    work = ROOT / "build" / args.platform
    work.mkdir(parents=True, exist_ok=True)
    from PySide6.QtCore import QLockFile
    lock = QLockFile(str(work / ".export.lock"))
    if not lock.tryLock(0):
        parser.error("Another export is already building. Wait for it to finish.")
    output = new_export_directory(args.output, args.platform)
    from PyInstaller.__main__ import run
    run([
        str(ROOT / "packaging" / "tars.spec"),
        "--distpath", str(output), "--workpath", str(work), "--noconfirm", "--clean",
    ])
    artifact = output / ("TARS.app" if args.platform == "macos" else "TARS")
    if not artifact.exists():
        raise RuntimeError("The build did not produce an application.")
    print(f"Export ready: {artifact}", flush=True)
    size = sum(path.stat().st_size for path in artifact.rglob("*")
               if path.is_file() and not path.is_symlink())
    print(f"Bundle size: {size / (1024 ** 2):.1f} MiB (French Piper voice included; downloaded models stored separately)", flush=True)
    lock.unlock()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
