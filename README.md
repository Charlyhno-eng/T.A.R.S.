![T.A.R.S.](public/tars-banner.png)

# **T.A.R.S.**

---

T.A.R.S. is my personal take on a Jarvis-like virtual robot assistant, designed to be controlled primarily through voice.

It can understand and respond in French or English, using lightweight local AI models for STT, TTS, and LLM tasks. Most interactions are processed locally and can run on CPU, keeping the system lightweight, private, and accessible without requiring powerful hardware.

For more complex tasks, T.A.R.S. can also rely on larger LLMs through APIs, combining local models with cloud-based AI when additional capabilities are needed.

The long-term goal is to make T.A.R.S. a voice-controlled interface for AI agents. You should be able to connect your own agents, tools, and services and control them naturally through speech.

This repository is my personal implementation, but you are free to clone it, modify it, and adapt it to your own needs. Use it as a foundation to connect your own AI agents and build your own voice-controlled AI system.

---

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Start

```bash
python app.py
```
