"""CPU limits and allocator cleanup for local inference."""

from __future__ import annotations

import ctypes
import gc
import os


def cpu_threads() -> int:
    """Leave room for the UI and avoid oversized inference thread pools."""
    available = (len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity")
                 else (os.cpu_count() or 1))
    return max(1, min(4, available))


def release_unused_memory(*, collect: bool = False) -> None:
    """Return unused Linux allocator pages; other allocators manage themselves."""
    if collect:
        gc.collect()
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except (AttributeError, OSError):
        return
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    trim(0)
