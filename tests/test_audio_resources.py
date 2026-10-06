from __future__ import annotations

import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import QApplication

from core.audio_recorder import AudioRecorder


class AudioRecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        for name, value in (
            ("temporary_directory", self.directory),
            ("QMediaDevices.defaultAudioInput", Mock()),
            ("QAudioSource", Mock()),
        ):
            patcher = patch("core.audio_recorder." + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
            if name.endswith("defaultAudioInput"):
                value.isNull.return_value = False
                value.isFormatSupported.return_value = True
            elif name == "QAudioSource":
                self.source = value
        self.device = self.source.start.return_value
        self.recorder = AudioRecorder()
        self.addCleanup(self.recorder.cancel)

    def test_recording_streams_to_disk_and_stop_drains_the_last_samples(self) -> None:
        chunks = [b"\x01\x00" * 2000, b"\xff\x7f" * 2000, b"\x00\x80" * 500]
        self.device.readAll.side_effect = [QByteArray(chunk) for chunk in chunks]
        self.recorder.start()
        self.recorder._read_audio()
        self.recorder._read_audio()
        path = self.recorder.stop()
        with wave.open(str(path), "rb") as recorded:
            self.assertEqual(recorded.getparams()[:3], (1, 2, 16000))
            self.assertEqual(recorded.readframes(recorded.getnframes()), b"".join(chunks))
        self.assertIsNone(self.recorder._output)
        self.assertFalse(self.recorder.recording)
        self.assertEqual(list(self.directory.iterdir()), [path])

    def test_cancel_short_recording_and_failed_start_remove_temporary_files(self) -> None:
        self.device.readAll.return_value = QByteArray(b"\x00\x00")
        self.recorder.start()
        self.recorder._read_audio()
        self.recorder.cancel()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.recorder.start()
        with self.assertRaisesRegex(RuntimeError, "trop court"):
            self.recorder.stop()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.source.start.return_value = None
        with self.assertRaisesRegex(RuntimeError, "démarrer"):
            self.recorder.start()
        self.assertEqual(list(self.directory.iterdir()), [])
        self.assertFalse(self.recorder.recording)
