"""Keep Arrow's dataset dependencies without Flight servers or the C++ SDK."""
from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_dependencies import arrow_runtime_binary, arrow_runtime_module

# Arrow's Cython extensions import Python modules dynamically.
hiddenimports = collect_submodules("pyarrow", filter=arrow_runtime_module)
binaries = [entry for entry in collect_dynamic_libs("pyarrow")
            if arrow_runtime_binary(entry[0])]
datas = [entry for entry in collect_data_files("pyarrow", excludes=[
    "tests/**", "include/**", "**/*.pxd", "**/*.pxi", "**/*.pyi", "**/*.pyx",
]) if arrow_runtime_binary(entry[0])]
