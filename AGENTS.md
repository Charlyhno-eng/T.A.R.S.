# T.A.R.S.

T.A.R.S. is a lightweight personal voice assistant and a foundation for building a Jarvis-style assistant. It is built with Python 3.12, PySide6, and a QML interface.

## Current capabilities

- Hold the central robot control to record speech; local Parakeet TDT 0.6B v3 transcribes it, GLM 5.3 Flash (Z.AI API, low reasoning effort) streams a concise reply, and local Pocket TTS streams speech directly to Qt audio while the rest of the reply arrives.
- English (default) and French are supported. The selected language persists. STT/TTS resources can be installed from the interface and then run offline; GLM needs internet access and a Z.AI API key.
- The interface has a semi-transparent midnight-blue background with simulated frosted glass, listening/processing/speaking states, an animated robot head, and settings for language, API key management, and saved startup full-screen mode or window dimensions and position.
- On Linux X11 (including Mint XFCE), Windows and macOS, a saved global shortcut supports hold-to-talk while hidden. Closing hides to the robot tray icon; its menu reopens or quits. Without a tray, closing quits normally.
- Settings can export a native executable bundle (Linux listed first). Build with `uv run --group build python scripts/build_app.py`; build each OS/architecture on its own platform. Exports use CPU-only PyTorch, scanned QML dependencies, and stripped Linux binaries; personal data stays outside the bundle. On Linux, `uv run python scripts/install_linux.py --clean-dist` moves the latest export to `~/.local/lib/tars`, registers an application-menu launcher, and removes older Linux exports.

## Project structure and workflow

- `src/core` contains the controller, audio capture, settings, asynchronous STT/LLM/TTS services, and desktop integration (X11 via `python-xlib`, Windows/macOS native shortcuts, and the Qt system tray). `src/providers/{stt,tts,llm}` contains provider implementations and adapter selection. `src/ui` contains QML screens, components, and theme.
- Python dependencies are managed with `uv` in `pyproject.toml`. Run with `uv run python src/app.py`; run tests with `uv run --project . --directory src python -m unittest discover -s ../tests`.
- Preferences and the private Z.AI key live in `~/.tars/config`; legacy checkout settings migrate once. Voice resources remain in `~/.tars/{stt,tts}`. `TARS_DATA_DIR` overrides this writable root; `core/paths.py` resolves bundled assets and OS temporary files.

## Working rules

- Follow existing conventions and keep changes within the requested scope.
- Keep this file concise; update it when durable project architecture or capabilities change.
