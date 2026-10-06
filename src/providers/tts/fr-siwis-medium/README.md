---
language:
- fr
license: cc-by-4.0
tags:
- tts
- piper
- onnx
- vits
library_name: piper
pipeline_tag: text-to-speech
---

# Piper TTS: fr_FR-siwis-medium

Medium-size French female voice.

## Model Details

| Field | Value |
|-------|-------|
| Architecture | VITS (end-to-end) |
| Format | ONNX |
| Language | French (France) |
| Gender | Female |
| Model Size | medium (~63 MB ONNX, ~15M params) |
| Sample Rate | 22050 Hz |
| License | CC BY 4.0 |

> **Note:** Piper uses the terms "medium", "high", etc. to refer to **model size**, not output quality.
> Medium models (~63 MB, ~15M params) and high models (~114 MB, ~28M params) both produce 22.05 kHz audio.

## Usage

### With piper-tts (GPL)

```python
from piper import PiperVoice

voice = PiperVoice.load("model.onnx")
for chunk in voice.synthesize("Hello, this is a test."):
    # chunk.audio_float_array contains float32 audio
    pass
```

### Standalone ONNX (MIT — no piper-tts dependency)

Requires `espeak-ng` installed (`brew install espeak-ng` / `apt install espeak-ng`).

```python
import json, subprocess, numpy as np, onnxruntime as ort, soundfile as sf
from huggingface_hub import hf_hub_download

model_id = "Trelis/piper-fr-fr-siwis-medium"
onnx_path = hf_hub_download(model_id, "model.onnx")
config_path = hf_hub_download(model_id, "model.onnx.json")

with open(config_path) as f:
    config = json.load(f)

session = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
phoneme_id_map = config["phoneme_id_map"]
espeak_voice = config["espeak"]["voice"]

def phonemize(text, voice):
    out = subprocess.run(
        ["espeak-ng", "-v", voice, "-q", "--ipa=2", "-x", text],
        capture_output=True, text=True,
    ).stdout.strip()
    return [list(line.replace("_", " ")) for line in out.split("\n") if line.strip()]

def to_ids(phonemes, pmap):
    ids = [pmap["^"][0], pmap["_"][0]]
    for p in phonemes:
        if p in pmap:
            ids.extend(pmap[p])
            ids.append(pmap["_"][0])
    ids.append(pmap["$"][0])
    return ids

text = "Hello, this is a test."
audio_chunks = []
for sentence in phonemize(text, espeak_voice):
    ids = to_ids(sentence, phoneme_id_map)
    if len(ids) < 3:
        continue
    audio = session.run(None, {
        "input": np.array([ids], dtype=np.int64),
        "input_lengths": np.array([len(ids)], dtype=np.int64),
        "scales": np.array([
            config["inference"]["noise_scale"],
            config["inference"]["length_scale"],
            config["inference"]["noise_w"],
        ], dtype=np.float32),
    })[0]
    audio_chunks.append(audio.squeeze())

audio = np.concatenate(audio_chunks).astype(np.float32)
sf.write("output.wav", audio, config["audio"]["sample_rate"])
```

## Fine-tuning

You can fine-tune this model on your own voice data using [Trelis Studio](https://studio.trelis.com). Piper models can be trained on custom datasets to create personalized voices.

## Attribution

Trained on [SIWIS French Speech Synthesis Database](https://datashare.is.ed.ac.uk/handle/10283/2353). Fine-tuned from lessac medium.

Re-hosted from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices/tree/main/fr/fr_FR/siwis/medium).
Original voice: `fr_FR-siwis-medium`
