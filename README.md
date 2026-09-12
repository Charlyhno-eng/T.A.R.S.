![T.A.R.S.](assets/tars-banner.png)

# **T.A.R.S.**

---

T.A.R.S. is my personal take on a Jarvis-like virtual robot assistant, designed to be controlled primarily through voice.

It can understand and respond in French or English, using lightweight local AI models for STT, TTS, and LLM tasks. Most interactions are processed locally and can run on CPU, keeping the system lightweight, private, and accessible without requiring powerful hardware.

For more complex tasks, T.A.R.S. can also rely on larger LLMs through APIs, combining local models with cloud-based AI when additional capabilities are needed.

The long-term goal is to make T.A.R.S. a voice-controlled interface for AI agents. You should be able to connect your own agents, tools, and services and control them naturally through speech.

This repository is my personal implementation, but you are free to clone it, modify it, and adapt it to your own needs. Use it as a foundation to connect your own AI agents and build your own voice-controlled AI system.

---

## See T.A.R.S. in action

![Interface](assets/tars-interface.png)

---

## Quick start

### Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python src/app.py
```

At the first launch, use the download button in the top-right corner. It installs
Pocket TTS (French voice Estelle) and Parakeet TDT 0.6B v3 into `~/.tars/`.
After the installation has completed, normal startup, transcription, and speech
generation only load these local files and do not require an Internet connection.

French is the default application language. Select `ENGLISH` from the top-right
language selector to switch the interface and voice. The first English selection
offers to download its compact local Pocket TTS voice; the choice is remembered.

Hold the central sphere while speaking; release it to have Parakeet transcribe
your voice and Pocket TTS repeat the transcription.
