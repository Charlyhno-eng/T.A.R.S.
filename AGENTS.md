# T.A.R.S.

T.A.R.S. is a lightweight personal voice assistant and a foundation for building a Jarvis-style assistant. It is built with Python 3.12, PySide6, and a QML interface.

## Current capabilities

- Hold the central robot control to record speech; local Parakeet TDT 0.6B v3 transcribes it, GLM 5.3 Flash (Z.AI API) generates a concise reply, and local Pocket TTS speaks it.
- English (default) and French are supported. The selected language persists. STT/TTS resources can be installed from the interface and then run offline; GLM needs internet access and a Z.AI API key.
- The interface shows listening, processing, and speaking states, an animated robot head, and settings for language and API key management.
- On Linux X11 (including Mint XFCE), a saved global shortcut supports hold-to-talk while the window is hidden. Closing hides to the robot system tray icon; its menu reopens the window or quits. Without a tray, closing quits normally.

## Project structure and workflow

- `src/core` contains the controller, audio capture, settings, asynchronous STT/LLM/TTS services, and desktop integration (`python-xlib` shortcuts and Qt system tray). `src/providers/{stt,tts,llm}` contains provider implementations and adapter selection. `src/ui` contains QML screens, components, and theme.
- Python dependencies are managed with `uv` in `pyproject.toml`. Run with `uv run python src/app.py`; run tests with `uv run pytest`.
- Preferences are stored in `config/config.toml`; the local, Git-ignored Z.AI key is stored in `config/llm_api_key`. Downloaded voice resources are stored under `~/.tars`.

## Working rules

- Follow existing conventions and keep changes within the requested scope.
- Keep this file concise; update it when durable project architecture or capabilities change.
