from __future__ import annotations

import logging
import uuid
import wave
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtMultimedia import QAudioFormat, QAudioSource, QMediaDevices
from core.paths import temporary_directory


logger = logging.getLogger("TARS.Recorder")


class AudioRecorder(QObject):
    """Capture 16 kHz mono microphone audio to a temporary WAV for Parakeet."""

    SAMPLE_RATE = 16_000

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._source: QAudioSource | None = None
        self._device = None
        self._output: wave.Wave_write | None = None
        self._output_path: Path | None = None
        self._bytes_recorded = 0

    @property
    def recording(self) -> bool:
        """Return whether microphone recording is active."""
        return self._source is not None

    def start(self) -> None:
        """Start microphone recording."""
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

        directory = temporary_directory("tars_stt")
        directory.mkdir(parents=True, exist_ok=True)
        self._output_path = directory / f"speech_{uuid.uuid4().hex}.wav"
        self._bytes_recorded = 0
        try:
            self._output = wave.open(str(self._output_path), "wb")
            self._output.setnchannels(1)
            self._output.setsampwidth(2)
            self._output.setframerate(self.SAMPLE_RATE)
            self._source = QAudioSource(device, audio_format, self)
            self._device = self._source.start()
            if self._device is None:
                raise RuntimeError("Impossible de démarrer le microphone.")
            self._device.readyRead.connect(self._read_audio)
        except Exception:
            self.cancel()
            raise

    def _read_audio(self) -> None:
        if self._device is not None and self._output is not None:
            payload = bytes(self._device.readAll().data())
            self._output.writeframesraw(payload)
            self._bytes_recorded += len(payload)

    def stop(self) -> Path:
        """Stop recording and return the audio file."""
        if not self.recording:
            raise RuntimeError("Aucun enregistrement n'est en cours.")

        try:
            self._read_audio()
            self._close_source()
            assert self._output is not None
            self._output.close()
            self._output = None
        except Exception:
            self.cancel()
            raise
        if self._bytes_recorded < self.SAMPLE_RATE // 5 * 2:
            self.cancel()
            raise RuntimeError("Enregistrement trop court. Maintenez le bouton pour parler.")
        assert self._output_path is not None
        output_path, self._output_path = self._output_path, None
        self._bytes_recorded = 0
        logger.info("Audio microphone écrit : %s", output_path)
        return output_path

    def cancel(self) -> None:
        """Stop recording and discard captured audio."""
        if self.recording:
            self._close_source()
        try:
            if self._output is not None:
                self._output.close()
        finally:
            self._output = None
            if self._output_path is not None:
                self._output_path.unlink(missing_ok=True)
                self._output_path = None
            self._bytes_recorded = 0

    def _close_source(self) -> None:
        assert self._source is not None
        self._source.stop()
        self._source.deleteLater()
        self._source = None
        self._device = None
