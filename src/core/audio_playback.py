from __future__ import annotations

from collections import deque
from math import gcd

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudioFormat, QAudioSink, QMediaDevices

try:
    from PySide6.QtMultimedia import QtAudio
except ImportError:  # Qt 6.6 used the old namespace.
    from PySide6.QtMultimedia import QAudio as QtAudio


class AudioPlayback(QObject):
    """Feed generated PCM directly to Qt without waiting for a complete WAV."""

    started = Signal()
    finished = Signal()
    errorOccurred = Signal(str)
    chunkConsumed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sink: QAudioSink | None = None
        self._device = None
        self._pending: deque[memoryview] = deque()
        self._input_finished = False
        self._started = False
        self._active = False
        self._written = 0
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._pump)

    def begin(self) -> None:
        self.stop()
        self._active = True

    def append(self, pcm: bytes, sample_rate: int) -> None:
        if not self._active or not pcm:
            return
        try:
            if self._sink is None:
                device = QMediaDevices.defaultAudioOutput()
                if device.isNull():
                    raise RuntimeError("No audio output device is available.")
                audio_format = QAudioFormat()
                audio_format.setSampleRate(sample_rate)
                audio_format.setChannelCount(1)
                audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
                if not device.isFormatSupported(audio_format):
                    audio_format = device.preferredFormat()
                self._sink = QAudioSink(device, audio_format, self)
                self._sink.setBufferSize(audio_format.bytesForDuration(100_000))
                self._device = self._sink.start()
                if self._device is None or self._sink.state() == QtAudio.State.StoppedState:
                    raise RuntimeError(f"Unable to start audio playback: {self._sink.error().name}.")
                self._timer.start()
            self._pending.append(memoryview(self._convert(pcm, sample_rate, self._sink.format())))
            self._pump()
        except Exception as exc:
            self._fail(str(exc))

    @staticmethod
    def _convert(pcm: bytes, sample_rate: int, audio_format: QAudioFormat) -> bytes:
        """Adapt mono float PCM when a device requires its native format."""
        sample_format = audio_format.sampleFormat()
        if (sample_rate == audio_format.sampleRate() and audio_format.channelCount() == 1
                and sample_format == QAudioFormat.SampleFormat.Float):
            return pcm
        import numpy as np
        from scipy.signal import resample_poly

        audio = np.frombuffer(pcm, dtype=np.float32)
        if sample_rate != audio_format.sampleRate():
            divisor = gcd(sample_rate, audio_format.sampleRate())
            audio = resample_poly(audio, audio_format.sampleRate() // divisor, sample_rate // divisor)
        if audio_format.channelCount() > 1:
            audio = np.repeat(audio[:, None], audio_format.channelCount(), axis=1)
        audio = np.clip(audio, -1.0, 1.0)
        if sample_format == QAudioFormat.SampleFormat.Int16:
            audio = (audio * 32767).astype(np.int16)
        elif sample_format == QAudioFormat.SampleFormat.Int32:
            audio = (audio.astype(np.float64) * 2147483647).astype(np.int32)
        elif sample_format == QAudioFormat.SampleFormat.UInt8:
            audio = ((audio + 1) * 127.5).astype(np.uint8)
        elif sample_format == QAudioFormat.SampleFormat.Float:
            audio = audio.astype(np.float32)
        else:
            raise RuntimeError("Unsupported audio output format.")
        return audio.tobytes()

    def end(self) -> None:
        if not self._active:
            return
        self._input_finished = True
        if self._sink is None:
            self._fail("TTS returned no audio.")
        else:
            self._pump()

    def _pump(self) -> None:
        sink = self._sink
        if sink is None or self._device is None:
            return
        if sink.state() == QtAudio.State.StoppedState:
            self._fail("Audio playback stopped unexpectedly.")
            return
        while self._pending and sink.bytesFree() > 0:
            chunk = self._pending[0]
            size = min(len(chunk), sink.bytesFree())
            size -= size % sink.format().bytesPerFrame()
            if not size:
                break
            # Some PySide versions reject memoryviews despite advertising them
            # in QIODevice.write. Copy only this small output-buffer fragment.
            written = self._device.write(bytes(chunk[:size]))
            if written < 0:
                self._fail("Unable to write audio to the output device.")
                return
            if written == 0:
                break
            self._written += written
            if written == len(chunk):
                self._pending.popleft()
                self.chunkConsumed.emit()
            else:
                # A view keeps partial writes from copying the remaining audio
                # at every timer tick (quadratic work for long sentences).
                self._pending[0] = memoryview(chunk)[written:]
            if not self._started:
                self._started = True
                self.started.emit()
        # Idle between chunks is an underrun, not the end of the response.
        if (self._input_finished and not self._pending
                and sink.state() == QtAudio.State.IdleState
                and sink.processedUSecs() >= sink.format().durationForBytes(self._written)):
            self.stop()
            self.finished.emit()

    def _fail(self, message: str) -> None:
        self.stop()
        self.errorOccurred.emit(message)

    def stop(self) -> None:
        self._timer.stop()
        sink, self._sink = self._sink, None
        self._device = None
        if sink is not None:
            sink.reset()
            sink.deleteLater()
        self._pending.clear()
        self._active = False
        self._input_finished = False
        self._started = False
        self._written = 0
