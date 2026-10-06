"""NeMo restoration with file-backed, full-precision inference weights.

Imported only when Parakeet is loaded, keeping NeMo out of UI startup imports.
"""

import torch
from nemo.core.connectors.save_restore_connector import SaveRestoreConnector


class InferenceSaveRestoreConnector(SaveRestoreConnector):
    @staticmethod
    def _load_state_dict_from_disk(model_weights, map_location="cpu"):
        # The supported checkpoint uses PyTorch's ZIP format. Keep compatibility
        # with older locally installed checkpoints that cannot be memory-mapped.
        try:
            return torch.load(model_weights, map_location=map_location,
                              weights_only=True, mmap=True)
        except RuntimeError as exc:
            if "mmap can only be used" not in str(exc):
                raise
            return torch.load(model_weights, map_location=map_location, weights_only=True)

    def load_instance_with_state_dict(self, instance, state_dict, strict):
        # Adopt the checkpoint storages instead of copying them into a second
        # model-sized allocation. No optimizer is used by the voice assistant.
        try:
            instance.load_state_dict(state_dict, strict=strict, assign=True)
        finally:
            instance._set_model_restore_state(is_being_restored=False)
