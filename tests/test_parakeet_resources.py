from __future__ import annotations

import importlib.util
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from core.stt_service import STTService
from providers.stt.parakeet import ParakeetProvider


class CheckpointTests(unittest.TestCase):
    def test_adopted_checkpoint_preserves_exact_weights_without_a_second_copy(self) -> None:
        import torch

        # Exercise the connector's real PyTorch storage handling without loading
        # NeMo's training imports into the unit-test process.
        source = Path(__file__).resolve().parents[1] / "src/providers/stt/checkpoint.py"
        spec = importlib.util.spec_from_file_location("tars_test_checkpoint", source)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {
            "nemo.core.connectors.save_restore_connector": SimpleNamespace(SaveRestoreConnector=object),
        }):
            spec.loader.exec_module(module)
        connector = module.InferenceSaveRestoreConnector()
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "weights.ckpt"
                expected = {"weight": torch.tensor([[0.25, -0.5]]), "bias": torch.tensor([0.125])}
                torch.save(expected, path, _use_new_zipfile_serialization=not legacy)
                weights = connector._load_state_dict_from_disk(path)
                instance = torch.nn.Linear(2, 1)
                instance._set_model_restore_state = Mock()
                connector.load_instance_with_state_dict(instance, weights, strict=True)
                self.assertEqual(instance.weight.data_ptr(), weights["weight"].data_ptr())
                torch.testing.assert_close(instance.weight, expected["weight"], rtol=0, atol=0)
                torch.testing.assert_close(instance(torch.tensor([[2., 1.]])),
                                           torch.tensor([[0.125]]), rtol=0, atol=0)
                instance._set_model_restore_state.assert_called_once_with(is_being_restored=False)
                del instance, weights  # Unmap before removing the file on Windows.


class ParakeetResourceTests(unittest.TestCase):
    def test_checkpoint_directory_lives_until_shutdown_and_failed_load_cleans_up(self) -> None:
        for fail in (False, True):
            with self.subTest(fail=fail), tempfile.TemporaryDirectory() as directory:
                provider = ParakeetProvider(data_directory=Path(directory))
                provider._model_path.touch()
                model = Mock()
                connector = Mock()
                extracted = []

                def unpack(*, path2file, out_folder):
                    path = Path(out_folder)
                    (path / "weights.ckpt").touch()
                    extracted.append(path)

                connector._unpack_nemo_file.side_effect = unpack
                restore = Mock(return_value=model)
                if fail:
                    restore.side_effect = RuntimeError("invalid checkpoint")
                nemo = SimpleNamespace(models=SimpleNamespace(ASRModel=SimpleNamespace(restore_from=restore)))
                torch = Mock()
                with patch.object(provider, "_import_nemo", return_value=nemo), patch(
                    "providers.stt.parakeet.release_unused_memory"
                ), patch.dict(sys.modules, {
                    "torch": torch,
                    "nemo.utils": SimpleNamespace(logging=Mock()),
                    "providers.stt.checkpoint": SimpleNamespace(
                        InferenceSaveRestoreConnector=Mock(return_value=connector)),
                }):
                    if fail:
                        with self.assertRaisesRegex(RuntimeError, "invalid checkpoint"):
                            provider.load()
                        self.assertFalse(extracted[0].exists())
                        self.assertIsNone(provider._model)
                    else:
                        provider.load()
                        provider.load()  # Reuse the mapping, not another extracted checkpoint.
                        restore.assert_called_once()
                        self.assertIs(restore.call_args.kwargs["save_restore_connector"], connector)
                        self.assertTrue(extracted[0].is_dir())
                        self.assertEqual(extracted[0].parent, provider._data_directory)
                        model.freeze.assert_called_once()
                        provider.shutdown()
                        self.assertFalse(extracted[0].exists())
                        self.assertIsNone(provider._model)
                    provider.shutdown()
                torch.set_num_threads.assert_called_once_with(provider.CPU_THREADS)

    def test_shutdown_defers_unmapping_until_a_slow_worker_finishes(self) -> None:
        entered, finish = threading.Event(), threading.Event()

        def initialize(**kwargs):
            entered.set()
            if not finish.wait(3):
                raise RuntimeError("Test timed out")

        with patch("core.stt_service.STTAdapter") as adapter:
            adapter.return_value.installed = True
            adapter.return_value.initialize.side_effect = initialize
            service = STTService()
            service.initialize_async()
            self.assertTrue(entered.wait(2))
            worker = next(iter(service._workers))
            try:
                # Model an operation that exceeds shutdown's join timeout.
                with patch.object(worker, "join"):
                    service.shutdown()
                adapter.return_value.shutdown.assert_not_called()
            finally:
                finish.set()
                worker.join(timeout=2)
                service.shutdown()
            self.assertFalse(worker.is_alive())
            adapter.return_value.shutdown.assert_called_once()
            self.assertFalse(service.initialized)
