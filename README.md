![T.A.R.S.](assets/tars-banner.png)

# T.A.R.S.

---

T.A.R.S. is an extremely lightweight local voice assistant built with Python, PySide6, and QML.
It uses Parakeet TDT 0.6B v3 for speech-to-text (STT), GLM 5.3 Flash for responses, and Pocket TTS for text-to-speech (TTS).

STT and TTS run locally on the CPU. GLM requires an internet connection and a Z.AI API key.
English is the default language, and Parakeet generally performs better in English than in French.
French remains available in Settings. The selected application and voice language is saved for later launches.

T.A.R.S. is not a finished product, but an accessible base for building a personal assistant.
The interface sends each transcription to GLM and speaks its response.
By default, GLM gives a brief spoken reply to reduce response time; you can ask for more detail when needed.
The app displays its name as “T.A.R.S.”, while the assistant uses “TARS” without periods in spoken responses.

---

## See T.A.R.S. in action

![Interface](assets/tars-interface.png)

---

## Quickstart

### Install

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.12, then run:

```bash
uv sync
```

### Configure GLM

Open the gear in the upper right to choose the application and voice language and enter your Z.AI API key. Save it there before using GLM. The key stays in the local `config/llm_api_key` file, which is ignored by Git and written with user-only permissions. You can replace or remove it from the same dialog. The configured model is `glm-5.3-flash`.

To use another LLM, implement the `LLMProvider.complete(text, language, history)` interface in `src/core/llm_service.py` and pass the provider to `LLMService`. For an OpenAI-compatible chat endpoint, you can instead supply a different `LLMConfig` to `GLMProvider`.

### Run

```bash
uv run python src/app.py
```

On first launch, use the download button to install the local models. On later launches, T.A.R.S. loads both local models before the central robot head becomes available. Once loading finishes, hold the head while speaking, then release it to hear the GLM response. The central control shows an animated 3D robot head inspired by the app mascot. Its shell and expression flex as T.A.R.S. listens, processes speech, and speaks, while the surrounding glow changes color with the state.

![Example](assets/tars-architecture.gif)

### Tests

Run the unit tests with:

```bash
PYTHONPATH=src uv run python -m unittest discover -s tests
```
