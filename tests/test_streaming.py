from __future__ import annotations

import io
import json
import os
import threading
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QCoreApplication, QIODevice
from PySide6.QtMultimedia import QAudioFormat
from PySide6.QtWidgets import QApplication

from core.audio_playback import AudioPlayback, QtAudio
from core.llm_service import LLMService, SpeechTextBuffer
from core.tts_service import TTSService
from providers.llm.glm_5_3_flash import LLMConfig, stream


def sse(payload: dict) -> bytes:
    return ("data: " + json.dumps(payload, ensure_ascii=False) + "\r\n\r\n").encode()


class StreamingHTTPTests(unittest.TestCase):
    def test_yields_content_before_completion_and_skips_reasoning(self) -> None:
        payload = io.BytesIO(
            b": heartbeat\r\n\r\n"
            + sse({"choices": [{"delta": {"reasoning_content": "private reasoning"}}]})
            + sse({"choices": [{"delta": {"content": "Bonjour. "}}]})
            + sse({"choices": [{"delta": {"content": "Ça va ?"}}]})
            + sse({"choices": [{"delta": {}, "finish_reason": "stop"}]})
            + b"data: [DONE]\r\n\r\n"
        )
        with patch("providers.llm.glm_5_3_flash._api_key", return_value="test-key"), patch(
            "providers.llm.glm_5_3_flash.urlopen", return_value=payload
        ) as request:
            chunks = stream("Salut", "fr", [])
            self.assertEqual(next(chunks), "Bonjour. ")
            self.assertLess(payload.tell(), len(payload.getvalue()))
            self.assertEqual(list(chunks), ["Ça va ?"])
            body = json.loads(request.call_args.args[0].data)
        self.assertTrue(body["stream"])
        self.assertEqual(body["reasoning_effort"], "low")
        self.assertIn("French", body["messages"][0]["content"])

    def test_invalid_empty_and_interrupted_streams_fail(self) -> None:
        fixtures = [
            (b"data: broken\n\n", "invalid stream"),
            (b"data: [DONE]\n\n", "empty response"),
            (sse({"choices": [{"delta": {"content": "partial"}}]}), "closed before"),
            (sse({"error": {"message": "failed"}}), "streaming error"),
            (sse({"choices": [{"delta": {}, "finish_reason": "network_error"}]}), "interrupted"),
        ]
        for payload, message in fixtures:
            with self.subTest(message=message), patch(
                "providers.llm.glm_5_3_flash._api_key", return_value="test-key"
            ), patch("providers.llm.glm_5_3_flash.urlopen", return_value=io.BytesIO(payload)):
                with self.assertRaisesRegex(RuntimeError, message):
                    list(stream("Hi", "en", []))

    def test_custom_backend_does_not_receive_glm_reasoning_option(self) -> None:
        with patch("providers.llm.glm_5_3_flash._api_key", return_value="test-key"), patch(
            "providers.llm.glm_5_3_flash.urlopen", return_value=io.BytesIO(
                sse({"choices": [{"delta": {"content": "OK"}, "finish_reason": "stop"}]})
            )
        ) as request:
            self.assertEqual(list(stream("Hi", "en", [], LLMConfig(model="custom"))), ["OK"])
            self.assertNotIn("reasoning_effort", json.loads(request.call_args.args[0].data))


class StreamingPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def wait_until(self, condition) -> None:
        deadline = time.monotonic() + 3
        while not condition() and time.monotonic() < deadline:
            QCoreApplication.processEvents()
            time.sleep(0.005)
        self.assertTrue(condition())

    def test_french_first_sentence_is_played_before_llm_finishes_reply(self) -> None:
        release = threading.Event()
        pcm_produced = threading.Event()

        class Provider:
            def stream(self, *args):
                yield "Bonjour je peux "
                yield "vous aider à préparer "
                yield "votre voyage. "
                if not release.wait(3):
                    raise RuntimeError("Test timed out")
                yield "Ça va ?"

        def generate(text, stop):
            pcm_produced.set()
            yield b"\x00" * 16, 24_000

        with patch("core.tts_service.TTSAdapter") as adapter, patch(
            "core.audio_playback.QMediaDevices.defaultAudioOutput"
        ) as output, patch("core.audio_playback.QAudioSink") as sink_class:
            audio_format = QAudioFormat()
            audio_format.setSampleRate(24_000)
            audio_format.setChannelCount(1)
            audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
            output.return_value.isNull.return_value = False
            output.return_value.isFormatSupported.return_value = True
            sink = sink_class.return_value
            sink.format.return_value = audio_format
            sink.error.return_value = QtAudio.Error.NoError
            sink.state.return_value = QtAudio.State.ActiveState
            sink.bytesFree.return_value = 4800
            sink.start.return_value.write.side_effect = len
            sink.processedUSecs.return_value = 0
            adapter.return_value.generate_stream.side_effect = generate
            tts = TTSService()
            tts._initialized = True
            llm = LLMService(provider=Provider())
            llm.sentenceReady.connect(tts.speak)
            llm.responseReady.connect(lambda _: tts.finish_response())
            started, finished = [], []
            tts.speechStarted.connect(lambda: started.append(True))
            tts.speechFinished.connect(lambda: finished.append(True))
            try:
                tts.begin_response()
                llm.respond("Salut", "fr")
                self.wait_until(lambda: bool(started))
                self.assertTrue(pcm_produced.is_set())
                adapter.return_value.generate_stream.assert_called_once_with(
                    "Bonjour je peux vous aider à préparer votre voyage.",
                    tts._stop_event,
                )
                self.assertFalse(release.is_set())
                self.assertFalse(finished)
                # A temporary underrun must not allow another conversation.
                sink.state.return_value = QtAudio.State.IdleState
                sink.processedUSecs.return_value = 1_000_000
                tts._playback._pump()
                self.assertTrue(tts._speaking)
                self.assertFalse(finished)
                release.set()
                self.wait_until(lambda: bool(finished))
                self.assertEqual([call.args[0] for call in adapter.return_value.generate_stream.call_args_list],
                                 ["Bonjour je peux vous aider à préparer votre voyage.", "Ça va ?"])
                self.assertEqual(llm._history[-1]["content"],
                                 "Bonjour je peux vous aider à préparer votre voyage. Ça va ?")
            finally:
                release.set()
                llm.cancel()
                tts.shutdown()

    def test_cancelled_llm_events_are_ignored_even_if_already_queued(self) -> None:
        llm = LLMService(provider=Mock(spec=["complete"]))
        received = []
        llm.sentenceReady.connect(received.append)
        old_id = llm._request_id
        llm.cancel()
        llm._deliver(old_id, "sentence", "stale speech")
        llm._deliver(llm._request_id, "sentence", "current speech")
        self.assertEqual(received, ["current speech"])

    def test_interrupted_request_closes_stream_without_saving_partial_history(self) -> None:
        closed = []

        class Provider:
            def stream(self, *args):
                try:
                    yield "First sentence. "
                    llm.cancel()
                    yield "Stale sentence. "
                finally:
                    closed.append(True)

        llm = LLMService(provider=Provider())
        sentences, replies = [], []
        llm.sentenceReady.connect(sentences.append)
        llm.responseReady.connect(replies.append)
        llm._respond_worker("Hi", "en", [])
        self.assertEqual(sentences, ["First sentence."])
        self.assertFalse(replies)
        self.assertFalse(llm._history)
        self.assertEqual(closed, [True])

    def test_audio_device_failure_cancels_worker_and_releases_busy_state(self) -> None:
        with patch("core.tts_service.TTSAdapter") as adapter, patch(
            "core.audio_playback.QMediaDevices.defaultAudioOutput"
        ) as output:
            output.return_value.isNull.return_value = True
            adapter.return_value.generate_stream.side_effect = lambda text, stop: iter([
                (b"\x00" * 16, 24_000)
            ])
            tts = TTSService()
            tts._initialized = True
            errors = []
            tts.errorOccurred.connect(errors.append)
            try:
                tts.begin_response()
                tts.speak("Hello.")
                self.wait_until(lambda: bool(errors))
                self.assertFalse(tts._speaking)
                self.assertTrue(tts._stop_event.is_set())
                self.assertEqual(errors, ["No audio output device is available."])
            finally:
                tts.shutdown()

    def test_cancelled_audio_and_generation_events_are_discarded(self) -> None:
        with patch("core.tts_service.TTSAdapter"), patch.object(AudioPlayback, "append") as append:
            tts = TTSService()
            tts._speaking = True
            old_session = tts._session
            errors = []
            tts.errorOccurred.connect(errors.append)
            tts.cancel_response()
            tts._on_audio_chunk(old_session, b"stale", 24_000)
            tts._on_generation_finished(old_session)
            tts._on_generation_failed(old_session, "stale error")
            append.assert_not_called()
            self.assertFalse(errors)
            tts.shutdown()

    def test_text_boundaries_preserve_decimals_and_words_in_both_languages(self) -> None:
        for text in ("It costs 3.50 euros. Next sentence.", "Ça coûte 3,50 euros. Voilà !"):
            buffer = SpeechTextBuffer()
            chunks = []
            for character in text:
                chunks.extend(buffer.add(character))
            chunks.append(buffer.finish())
            self.assertEqual(" ".join(chunks), text)
            self.assertEqual(len(chunks), 2)
        buffer = SpeechTextBuffer()
        text = "A long sentence " * 60
        chunks = buffer.add(text)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 400 for chunk in chunks))
        self.assertEqual(" ".join([*chunks, buffer.finish()]), text.strip())

    def test_french_opening_keeps_clauses_together_across_token_boundaries(self) -> None:
        text = (
            "Bien sûr, je peux vous aider : le billet coûte 3,50 euros et nous "
            "pouvons préparer votre prochain voyage ensemble."
        )
        for token_size in (1, 7, 40):
            with self.subTest(token_size=token_size):
                buffer = SpeechTextBuffer(early_fragment=False)
                for start in range(0, len(text), token_size):
                    self.assertEqual(buffer.add(text[start:start + token_size]), [])
                self.assertEqual(buffer.add(" La suite"), [text])
                self.assertEqual(buffer.finish(), "La suite")
                self.assertEqual(buffer.finish(), "")

    def test_french_long_opening_still_splits_at_clauses_or_words(self) -> None:
        for text in (
            "Nous pouvons examiner ces détails ensemble " * 6 + ", puis continuer " * 20,
            "Nous pouvons examiner ces détails ensemble " * 25,
        ):
            with self.subTest(text=text):
                buffer = SpeechTextBuffer(early_fragment=False)
                chunks = []
                for character in text:
                    chunks.extend(buffer.add(character))
                self.assertTrue(chunks)
                self.assertTrue(all(len(chunk) <= buffer.WORD_LIMIT for chunk in chunks))
                self.assertEqual(" ".join([*chunks, buffer.finish()]), text.strip())

    def test_sentences_after_opening_keep_their_clauses_and_intonation(self) -> None:
        for text in (
            "I can help: tell me what you need; we can work through the details together "
            "and find a simple solution that suits your plans for tomorrow.",
            "Je peux vous aider : dites-moi ce dont vous avez besoin ; nous pourrons "
            "examiner les détails ensemble et trouver une solution adaptée à vos projets.",
        ):
            with self.subTest(text=text):
                self.assertGreater(len(text), 120)
                buffer = SpeechTextBuffer()
                self.assertEqual(buffer.add("Hello. "), ["Hello."])
                for character in text:
                    self.assertEqual(buffer.add(character), [])
                self.assertEqual(buffer.add(" "), [text])
                self.assertEqual(buffer.finish(), "")

    def test_long_sentences_prefer_clause_boundaries_and_keep_all_words(self) -> None:
        buffer = SpeechTextBuffer()
        self.assertEqual(buffer.add("Hello. "), ["Hello."])
        clause = "Let's examine the details " * 8 + ","
        tail = " and then choose the solution that works best for you"
        text = clause + tail
        self.assertEqual(buffer.add(text), [clause])
        self.assertEqual(buffer.finish(), tail.strip())

    def test_opening_fragment_preserves_words_with_arbitrary_token_boundaries(self) -> None:
        for text in (
            "I can help you plan a wonderful trip with your family tomorrow.",
            "Je peux vous aider à préparer votre prochain voyage en famille.",
            "The price is 3.50 euros and the address is https://example.com/page today.",
        ):
            with self.subTest(text=text):
                buffer = SpeechTextBuffer()
                chunks = []
                for character in text:
                    chunks.extend(buffer.add(character))
                self.assertEqual(len(chunks), 1)
                self.assertLessEqual(len(chunks[0]), buffer.FIRST_CHUNK_LIMIT)
                chunks.append(buffer.finish())
                self.assertEqual(" ".join(chunks), text)

    def test_opening_clause_starts_early_and_short_or_unbroken_text_waits(self) -> None:
        for opening in ("Bien sûr, ", "Of course: "):
            with self.subTest(opening=opening):
                buffer = SpeechTextBuffer()
                self.assertEqual(buffer.add(opening), [opening.strip()])
                self.assertEqual(buffer.add("the rest is still arriving"), [])
                self.assertEqual(buffer.finish(), "the rest is still arriving")
        for text in ("Salut", "x" * 80):
            buffer = SpeechTextBuffer()
            self.assertEqual(buffer.add(text), [])
            self.assertEqual(buffer.finish(), text)

    def test_pcm_conversion_supports_native_stereo_integer_output(self) -> None:
        import numpy as np

        audio_format = QAudioFormat()
        audio_format.setSampleRate(48_000)
        audio_format.setChannelCount(2)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        pcm = np.zeros(240, dtype=np.float32).tobytes()
        converted = AudioPlayback._convert(pcm, 24_000, audio_format)
        self.assertEqual(len(converted), 480 * 2 * 2)
        self.assertTrue(np.all(np.frombuffer(converted, dtype=np.int16) == 0))

    def test_partial_writes_are_retried_and_buffered_tail_must_drain(self) -> None:
        playback = AudioPlayback()
        playback.begin()
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24_000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
        sink = Mock()
        sink.format.return_value = audio_format
        sink.state.return_value = QtAudio.State.IdleState
        sink.bytesFree.return_value = 16
        sink.processedUSecs.return_value = 0
        writer = Mock()
        writer.write.side_effect = [4, 0, 12]
        playback._sink, playback._device = sink, writer
        pcm = b"\x00" * 16
        playback._pending.append(memoryview(pcm))
        finished = []
        playback.finished.connect(lambda: finished.append(True))
        playback._pump()
        self.assertEqual(len(playback._pending[0]), 12)
        self.assertIs(playback._pending[0].obj, pcm)
        playback.end()
        self.assertFalse(finished)
        sink.processedUSecs.return_value = audio_format.durationForBytes(16)
        playback._pump()
        self.assertEqual(finished, [True])

    def test_pcm_views_can_be_written_to_a_real_qt_device(self) -> None:
        audio_format = QAudioFormat()
        audio_format.setSampleRate(24_000)
        audio_format.setChannelCount(1)
        audio_format.setSampleFormat(QAudioFormat.SampleFormat.Float)
        sink = Mock()
        sink.format.return_value = audio_format
        sink.state.return_value = QtAudio.State.ActiveState
        sink.bytesFree.return_value = 4
        output = QBuffer()
        self.assertTrue(output.open(QIODevice.OpenModeFlag.WriteOnly))
        playback = AudioPlayback()
        playback.begin()
        playback._sink, playback._device = sink, output
        pcm = b"\x00\x00\x80\x3f" * 32
        playback._pending.append(memoryview(pcm))
        playback._pump()
        self.assertEqual(bytes(output.data()), pcm)
        self.assertFalse(playback._pending)
        playback.stop()

    def test_fast_synthesis_is_bounded_by_playback_and_cancellation_unblocks_it(self) -> None:
        produced = []
        received = []
        closed = threading.Event()
        chunks = [bytes([index]) * 4800 for index in range(20)]

        def generate(text, stop):
            try:
                for pcm in chunks:
                    produced.append(pcm)
                    yield pcm, 24_000
            finally:
                closed.set()

        with patch("core.tts_service.TTSAdapter") as adapter, patch.object(
            AudioPlayback, "append", side_effect=lambda pcm, rate: received.append(pcm)
        ):
            adapter.return_value.generate_stream.side_effect = generate
            tts = TTSService()
            tts._initialized = True
            try:
                tts.begin_response()
                tts.speak("A much longer response.")
                self.wait_until(lambda: len(received) == tts.MAX_PENDING_CHUNKS
                                and len(produced) == tts.MAX_PENDING_CHUNKS + 1)
                self.assertEqual(received, chunks[:tts.MAX_PENDING_CHUNKS])
                # Draining one provider chunk permits exactly one more packet.
                tts._playback.chunkConsumed.emit()
                self.wait_until(lambda: len(received) == tts.MAX_PENDING_CHUNKS + 1
                                and len(produced) == tts.MAX_PENDING_CHUNKS + 2)
                self.assertEqual(received, chunks[:tts.MAX_PENDING_CHUNKS + 1])
                tts.cancel_response()
                tts._worker.join(timeout=1)
                self.assertFalse(tts._worker.is_alive())
                self.assertTrue(closed.is_set())
            finally:
                tts.shutdown()
