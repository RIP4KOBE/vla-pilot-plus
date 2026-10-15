import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import yaml


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))
os.chdir(RDT_ROOT)


def _selected_suites(raw_suite):
    suites = [suite.strip() for suite in raw_suite.split(",") if suite.strip()]
    if not suites:
        raise SystemExit("Smoke test requires at least one selected LIBERO suite.")
    return suites


def _require_consumer_stats(raw_suite):
    selected_suites = _selected_suites(raw_suite)
    stats_path = RDT_ROOT / "configs" / "dataset_stat.json"
    with stats_path.open("r") as f:
        dataset_stat = json.load(f)
    missing = [suite for suite in selected_suites if suite not in dataset_stat]
    if missing:
        raise SystemExit(
            "Consumer smoke test requires stats for suites {!r} in {}. "
            "Run stats computation before using --consumer.".format(
                missing,
                stats_path,
            )
        )


class SmokeTokenizer:
    pad_token_id = 0

    def __call__(self, text, return_tensors="pt", padding="longest", truncation=False):
        token_ids = [1] + [min(1000, ord(ch)) for ch in text[:64]]
        return SimpleNamespace(input_ids=torch.tensor([token_ids], dtype=torch.long))


class SmokeImageProcessor:
    image_mean = [0.5, 0.5, 0.5]
    size = {"height": 384, "width": 384}

    def preprocess(self, image, return_tensors="pt"):
        image = image.resize((384, 384))
        array = np.asarray(image).astype(np.float32) / 255.0
        tensor = torch.from_numpy(array).permute(2, 0, 1)
        return {"pixel_values": tensor.unsqueeze(0)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default=os.environ.get("RDT_LIBERO_SUITES", "libero_10"))
    parser.add_argument("--data-root", default=os.environ.get("RDT_LIBERO_DATA_ROOT", "/mnt/data/hf_cache/hub"))
    parser.add_argument("--index", type=int, default=0)
    parser.add_argument("--step-id", type=int, default=0)
    parser.add_argument("--consumer", action="store_true")
    args = parser.parse_args()

    os.environ["RDT_HDF5_BACKEND"] = "libero"
    os.environ["RDT_LIBERO_SUITES"] = args.suite
    os.environ["RDT_LIBERO_DATA_ROOT"] = args.data_root

    if args.consumer:
        _require_consumer_stats(args.suite)

    from data.hdf5_vla_dataset import HDF5VLADataset

    dataset = HDF5VLADataset()
    sample = dataset.get_item(index=args.index, step_id=args.step_id)
    print("dataset_name:", sample["meta"]["dataset_name"])
    print("instruction:", sample["meta"]["instruction"])
    print("state:", sample["state"].shape, sample["state"].dtype)
    print("actions:", sample["actions"].shape, sample["actions"].dtype)
    print("active_indices:", np.where(sample["state_indicator"] > 0)[0].tolist())
    print("cam_high:", sample["cam_high"].shape, sample["cam_high_mask"].tolist())
    print("cam_right_wrist:", sample["cam_right_wrist"].shape, sample["cam_right_wrist_mask"].tolist())
    print("cam_left_wrist:", sample["cam_left_wrist"].shape, sample["cam_left_wrist_mask"].tolist())
    assert sample["state"].shape == (1, 128)
    assert sample["actions"].shape == (64, 128)
    assert np.where(sample["state_indicator"] > 0)[0].tolist() == [10, 30, 31, 32, 33, 34, 35, 36, 37, 38]
    assert sample["cam_high"].shape[0] == 2
    assert sample["cam_right_wrist"].shape[0] == 2
    assert sample["cam_left_wrist"].shape == (2, 0, 0, 0)
    assert sample["cam_left_wrist_mask"].tolist() == [False, False]

    if args.consumer:
        with open(RDT_ROOT / "configs" / "base.yaml", "r") as f:
            config = yaml.safe_load(f)
        from train.dataset import DataCollatorForVLAConsumerDataset, VLAConsumerDataset

        consumer = VLAConsumerDataset(
            config=config["dataset"],
            tokenizer=SmokeTokenizer(),
            image_processor=SmokeImageProcessor(),
            num_cameras=config["common"]["num_cameras"],
            img_history_size=config["common"]["img_history_size"],
            image_size=None,
            auto_adjust_image_brightness=False,
            image_aug=False,
            dataset_type="finetune",
            cond_mask_prob=0.0,
            cam_ext_mask_prob=-1.0,
            state_noise_snr=None,
            use_hdf5=True,
            use_precomp_lang_embed=False,
        )
        batch = DataCollatorForVLAConsumerDataset(SmokeTokenizer())([consumer[0], consumer[1]])
        print("consumer.states:", tuple(batch["states"].shape))
        print("consumer.actions:", tuple(batch["actions"].shape))
        print("consumer.images:", tuple(batch["images"].shape))
        assert tuple(batch["states"].shape) == (2, 1, 128)
        assert tuple(batch["actions"].shape) == (2, 64, 128)
        assert tuple(batch["images"].shape[:2]) == (2, 6)


if __name__ == "__main__":
    main()
