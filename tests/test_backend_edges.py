from __future__ import annotations

import io
import json
from urllib.error import HTTPError, URLError
from unittest.mock import Mock, patch

from PySide6.QtCore import QProcess
from PySide6.QtMultimedia import QAudioFormat

from backend_support import BackendTestCase
from core.audio_playback import AudioPlayback
from core.export_service import ExportService
from core.runtime_resources import cpu_threads, release_unused_memory
from providers.llm.glm_5_3_flash import GLMProvider, complete, stream


class BackendEdgeTests(BackendTestCase):
    def test_http_failures_and_invalid_payloads_are_user_facing(self):
        cases = ((HTTPError("test", 401, "Unauthorized", None, None), "HTTP 401"),
                 (URLError("Offline"), "connect"))
        with patch("providers.llm.glm_5_3_flash._api_key", return_value="test-key"):
            for error, message in cases:
                for request in (lambda: complete("Hi", "en", []), lambda: list(stream("Hi", "en", []))):
                    with self.subTest(error=error), patch("providers.llm.glm_5_3_flash.urlopen", side_effect=error):
                        with self.assertRaisesRegex(RuntimeError, message):
                            request()
            for payload in ({}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
                with patch("providers.llm.glm_5_3_flash.urlopen", return_value=io.BytesIO(json.dumps(payload).encode())):
                    with self.assertRaisesRegex(RuntimeError, "invalid response"):
                        complete("Hi", "en", [])
            for payload in (b"\xff\n", b'data: {"choices":[{"delta":{"content":42}}]}\n\n',
                            b'data: {"choices":[]}\n\ndata: [DONE]\n\n'):
                with patch("providers.llm.glm_5_3_flash.urlopen", return_value=io.BytesIO(payload)):
                    with self.assertRaises(RuntimeError):
                        list(stream("Hi", "en", []))
        provider = GLMProvider()
        with patch("providers.llm.glm_5_3_flash.complete", return_value="OK") as request:
            self.assertEqual(provider.complete("Hi", "en", []), "OK")
            request.assert_called_once_with("Hi", "en", [], provider.config)
        with patch("providers.llm.glm_5_3_flash.stream", return_value=iter(["OK"])):
            self.assertEqual(list(provider.stream("Hi", "en", [])), ["OK"])

    def test_export_cancel_finish_error_and_forced_shutdown(self):
        with patch("core.export_service.QProcess") as process_type:
            process_type.NormalExit = QProcess.NormalExit
            process_type.FailedToStart = QProcess.FailedToStart
            process = process_type.return_value
            process.readAllStandardOutput.return_value = b"x" * 13000
            service = ExportService()
            with patch("core.export_service.QFileDialog.getExistingDirectory", return_value=""), patch(
                "core.export_service.importlib.util.find_spec", return_value=object()
            ):
                service.start(service.platform)
                process.start.assert_not_called()
            service._read_output()
            self.assertEqual(len(service.log), 12000)
            service._destination = "/tmp/export"
            service._running = True
            with patch("core.export_service.QDesktopServices.openUrl") as open_url:
                service._finished(0, QProcess.NormalExit)
                open_url.assert_called_once()
                self.assertFalse(service.running)
                service._finished(2, QProcess.CrashExit)
                self.assertIn("exit 2", service.log)
            process.errorString.return_value = "Failed to start"
            service._running = True
            service._error(QProcess.FailedToStart)
            self.assertFalse(service.running)
            self.assertIn("Failed to start", service.log)
            service._running = True
            service._error(QProcess.ReadError)
            self.assertTrue(service.running)
            process.waitForFinished.side_effect = [False, True]
            service.shutdown()
            process.terminate.assert_called_once()
            process.kill.assert_called_once()

    def test_allocator_fallback_and_cpu_limits(self):
        for affinity, expected in ((set(), 1), ({0}, 1), (set(range(64)), 4)):
            with patch("core.runtime_resources.os.sched_getaffinity", return_value=affinity, create=True):
                self.assertEqual(cpu_threads(), expected)
        with patch("core.runtime_resources.ctypes.CDLL", side_effect=OSError), patch(
            "core.runtime_resources.gc.collect"
        ) as collect:
            release_unused_memory(collect=True)
            collect.assert_called_once()

    def test_pcm_integer_conversions_and_unsupported_output(self):
        import numpy as np
        pcm = np.array([-1., 0., 1.], dtype=np.float32).tobytes()
        for sample_format, dtype, expected in ((QAudioFormat.Int32, np.int32, [-2147483647, 0, 2147483647]),
                                               (QAudioFormat.UInt8, np.uint8, [0, 127, 255])):
            audio_format = QAudioFormat()
            audio_format.setSampleRate(16000)
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(sample_format)
            converted = AudioPlayback._convert(pcm, 16000, audio_format)
            np.testing.assert_array_equal(np.frombuffer(converted, dtype=dtype), expected)
        audio_format.setSampleFormat(QAudioFormat.Unknown)
        with self.assertRaisesRegex(RuntimeError, "Unsupported"):
            AudioPlayback._convert(pcm, 16000, audio_format)
        playback = AudioPlayback()
        playback.append(pcm, 16000)
        playback.end()
        playback.begin()
        errors = []
        playback.errorOccurred.connect(errors.append)
        playback.end()
        self.assertEqual(errors, ["TTS returned no audio."])
