from contextlib import contextmanager
from pathlib import Path
import sys
from types import SimpleNamespace

import torch


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


class _AutocastTrackingAccelerator:
    def __init__(self):
        self.inside_autocast = False
        self.is_main_process = True

    @contextmanager
    def autocast(self):
        self.inside_autocast = True
        try:
            yield
        finally:
            self.inside_autocast = False

    def gather_for_metrics(self, values):
        return values

    def gather(self, value):
        return value


class _DummyVisionEncoder:
    hidden_size = 4

    def __call__(self, images):
        return torch.ones((images.shape[0], self.hidden_size), dtype=images.dtype)


class _DummyTextEncoder:
    def __call__(self, input_ids, attention_mask):
        batch_size, seq_len = input_ids.shape
        return {
            "last_hidden_state": torch.ones(
                (batch_size, seq_len, 4),
                dtype=torch.bfloat16,
            )
        }


class _AutocastRequiredRDT:
    def __init__(self, accelerator):
        self.accelerator = accelerator

    def eval(self):
        pass

    def train(self):
        pass

    def predict_action(self, *, state_tokens, action_mask, **_kwargs):
        assert self.accelerator.inside_autocast, "predict_action called outside accelerator.autocast()"
        return torch.zeros(
            (state_tokens.shape[0], 2, action_mask.shape[-1]),
            dtype=torch.float32,
        )


def test_sampling_predict_action_runs_under_accelerator_autocast():
    from train.sample import log_sample_res

    accelerator = _AutocastTrackingAccelerator()
    batch = {
        "data_indices": [0],
        "ctrl_freqs": torch.tensor([20]),
        "state_norm": torch.ones((1, 3)),
        "images": torch.zeros((1, 1, 3, 2, 2)),
        "states": torch.zeros((1, 1, 3)),
        "actions": torch.zeros((1, 2, 3)),
        "state_elem_mask": torch.ones((1, 3)),
        "lang_attn_mask": torch.ones((1, 2), dtype=torch.bool),
        "input_ids": torch.ones((1, 2), dtype=torch.long),
    }

    result = log_sample_res(
        text_encoder=_DummyTextEncoder(),
        vision_encoder=_DummyVisionEncoder(),
        rdt=_AutocastRequiredRDT(accelerator),
        args=SimpleNamespace(num_sample_batches=1, precomp_lang_embed=False),
        accelerator=accelerator,
        weight_dtype=torch.bfloat16,
        dataset_id2name={0: "dummy"},
        dataloader=[batch],
        logger=SimpleNamespace(info=lambda *_args, **_kwargs: None),
    )

    assert result["overall_avg_sample_mse"] == 0.0
