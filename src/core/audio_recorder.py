from __future__ import annotations

import logging
import uuid
import wave
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices


logger = logging.getLogger("TARS.Recorder")


class AudioRecorder(QObject):
    """Capture microphone mono 16 kHz vers un WAV temporaire pour Parakeet."""

    SAMPLE_RATE = 16_000

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source: QAudioSource | None = None
        self._device = None
        self._chunks: list[bytes] = []

    @property
    def recording(self) -> bool:
        return self._source is not None

    def start(self) -> None:
        if self.recording:
            return

        device = QMediaDevices.defaultAudioInput()
        if device.isNull():
            raise RuntimeError("Aucun microphone n'est disponible.")

        audio_format = QAudioFormat()
        audio_format.setSampleRate(self.SAMPLE_RATE)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        if not device.isFormatSupported(audio_format):
            raise RuntimeError(
                "Le microphone ne prend pas en charge le format 16 kHz mono requis."
            )

        self._chunks = []
        self._source = QAudioSource(device, audio_format, self)
        self._device = self._source.start()
        if self._device is None:
            self._source.deleteLater()
            self._source = None
            raise RuntimeError("Impossible de démarrer le microphone.")
        self._device.readyRead.connect(self._read_audio)

    def _read_audio(self) -> None:
        if self._device is not None:
            self._chunks.append(bytes(self._device.readAll().data()))

    def stop(self) -> Path:
        if not self.recording:
            raise RuntimeError("Aucun enregistrement n'est en cours.")

        assert self._source is not None
        self._source.stop()
        self._source.deleteLater()
        self._source = None
        self._device = None

        payload = b"".join(self._chunks)
        self._chunks = []
        if len(payload) < self.SAMPLE_RATE // 5 * 2:
            raise RuntimeError("Enregistrement trop court. Maintenez le bouton pour parler.")

        directory = Path("/tmp") / "tars_stt"
        directory.mkdir(parents=True, exist_ok=True)
        output_path = directory / f"speech_{uuid.uuid4().hex}.wav"
        with wave.open(str(output_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.SAMPLE_RATE)
            output.writeframes(payload)
        logger.info("Audio microphone écrit : %s", output_path)
        return output_path
