"""Move an exported Linux bundle out of the checkout and register its launcher."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from core.linux_install import clean_linux_exports, install_bundle, linux_exports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, nargs="?", help="TARS bundle folder (default: latest Linux export in dist)")
    parser.add_argument("--clean-dist", action="store_true", help="Remove earlier generated Linux exports after installation")
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        parser.error("This installer requires Linux.")
    exports = linux_exports(ROOT / "dist")
    bundle = args.bundle or (exports[-1] / "TARS" if exports else None)
    if bundle is None:
        parser.error("No Linux export found. Run scripts/build_app.py --platform linux first.")
    installation = Path.home() / ".local" / "lib" / "tars"
    data_home = Path(os.environ.get("XDG_DATA_HOME", ""))
    if not data_home.is_absolute():
        data_home = Path.home() / ".local" / "share"
    launcher = install_bundle(bundle, installation, data_home / "applications")
    print(f"Installed: {installation / 'TARS'}\nApplication menu entry: {launcher}", flush=True)
    if args.clean_dist:
        clean_linux_exports(ROOT / "dist")
        print("Cleaned generated Linux exports in dist.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
