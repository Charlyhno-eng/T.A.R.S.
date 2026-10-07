"""Dynamic imports and non-code resources used by the CPU voice application.

Let PyInstaller follow ordinary imports instead of collecting whole packages.
Optional training, server and GPU integrations are not application features.
"""
from pathlib import PurePosixPath

HIDDEN_IMPORTS = (
    "PySide6.QtQuick", "PySide6.QtMultimedia", "scipy.io.wavfile",
    # NeMo restores this class by its checkpoint's Hydra target string.
    "nemo.collections.asr.models.rnnt_bpe_models",
    "nemo.collections.asr.modules",
    # Piper loads its native phonemizer inside the synthesis path.
    "piper.espeakbridge",
)

EXCLUDED_MODULES = (
    "PyQt5", "PyQt6", "PySide2", "tkinter", "IPython", "pytest",
    "piper.train", "piper.http_server", "piper.__main__",
    "pocket_tts.main", "pocket_tts.__main__",
    # CPU decoding does not use CUDA Python; NeMo guards this optional import.
    "cuda",
    # Experiment tracking is not used by the assistant.
    "wandb",
    # NeMo imports PyArrow datasets, but never its RPC server or query-plan API.
    "pyarrow.flight", "pyarrow._flight", "pyarrow.substrait", "pyarrow._substrait",
)

DATA_FILES = {
    # Keep all phonemizer languages: English/French text may switch languages.
    "piper": ["espeak-ng-data/**"],
    "pocket_tts": ["config/english.yaml", "config/french_24l.yaml"],
    "hydra": ["conf/**"],
}


def arrow_runtime_module(name: str) -> bool:
    return not (name == "pyarrow.tests" or name.startswith("pyarrow.tests.")
                # pkgutil also mistakes unversioned helper libraries for modules.
                or name in {"pyarrow.libarrow_python_flight", "pyarrow._pyarrow_cpp_tests"}
                or any(name == excluded or name.startswith(excluded + ".")
                       for excluded in EXCLUDED_MODULES if excluded.startswith("pyarrow.")))


def arrow_runtime_binary(source: str) -> bool:
    name = PurePosixPath(source.replace("\\", "/")).name.lower()
    # libarrow_python links Substrait directly even without its Python API.
    return "arrow_flight" not in name and "arrow_python_flight" not in name


def runtime_payload(entry: tuple[str, str, str]) -> bool:
    """Omit framework test executables while preserving native runtime tools."""
    path = PurePosixPath(entry[0].replace("\\", "/"))
    return not (
        not arrow_runtime_binary(entry[0])
        or (path.parts[:1] == ("pyarrow",) and path.name.startswith("_pyarrow_cpp_tests"))
        or path.parts[:2] == ("torch", "test")
        or (path.parts[:2] == ("torch", "bin")
            and (path.name.startswith("test_") or path.name.endswith("Test")))
    )
