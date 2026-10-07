# T.A.R.S.

T.A.R.S. is a personal voice assistant and extensible Jarvis-style foundation, built with Python 3.12, PySide6 and QML.

## Capabilities

- Hold-to-talk uses local Parakeet TDT 0.6B v3 and streams concise GLM 5.3 Flash replies through the Z.AI API. Local TTS starts on a complete opening sentence in French or a short fragment in English while GLM continues, then follows sentence boundaries. Piper is the default speech engine; Pocket TTS is also supported and included in exports.
- English and French are supported, and language selection persists. French Piper uses Siwis medium (`fr_FR-siwis-medium`); all STT/TTS resources download from the interface into user data and work offline after installation. Voice models are not stored in the repository or application bundle. GLM requires internet and a Z.AI API key.
- The frameless, responsive interface has animated listening/processing/speaking states, saved window or full-screen startup settings, and a latest-exchange panel. Settings manage models, language, API credentials and application export.
- A saved global hold-to-talk shortcut and tray operation are supported on Linux X11, Windows and macOS. Without a tray, closing quits.

## Structure and workflow

- `src/core` contains services, settings, audio and desktop integration; `src/providers/{stt,tts,llm}` contains provider implementations and adapters; `src/ui` contains the QML interface.
- Manage dependencies with `uv` and `pyproject.toml`. Run with `uv run python src/app.py`; run tests with `uv run --project . --directory src python -m unittest discover -s ../tests`.
- Settings and the private Z.AI key live in `~/.tars/config`; voice resources live in `~/.tars/{stt,tts}`. `TARS_DATA_DIR` overrides this root; `core/paths.py` resolves bundled assets and OS temporary files.
- Parakeet releases idle weights after validation/transcription and reuses its disk extraction until all STT workers stop at shutdown. Hidden/minimized windows release TTS after synthesis; services remain ready to reload locally. TTS bounds queued audio without changing provider chunk boundaries.
- Build on each target OS/architecture with `uv run --group build python scripts/build_app.py`. Linux install: `uv run python scripts/install_linux.py --clean-dist`.
- Exports follow runtime imports; preserve analyzed NeMo sources for TorchScript, Hydra plugins, voice configurations and phonemizer data.

## Working rules

- Follow existing conventions and keep changes within the requested scope.
- Keep this file concise; update it when durable project architecture or capabilities change.
