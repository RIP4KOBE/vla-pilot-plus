"""Run the pinned main trainer with process-local corrected demo inputs.

The live slow-loop registry, tickets, source specifications and Python modules
are never written. Full-policy SFT, accumulation and checkpoint recovery are
the native main implementation.
"""
import os
from pathlib import Path
import sys

from .config import cpu_environment
from .demonstration_inputs import MARKER, PolicyInputDataset, policy_image
from .io import digest, read_json, write_json


class CoFTInputView:
    def __init__(self, dataset, source, runtime):
        self.dataset = dataset
        self.runtime = runtime
        self.corrected = PolicyInputDataset(dataset, source, runtime) if source else None

    def __getattr__(self, name):
        dataset = self.__dict__.get("dataset")
        if dataset is None:
            raise AttributeError(name)
        return getattr(dataset, name)

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        if self.corrected is not None:
            row = self.corrected[index]
            row.pop(MARKER)
        else:
            row = dict(self.dataset[index])
            # Original v44 replay already has native policy state and image
            # orientation. Only match the benchmark's 128x128 camera size.
            for key in ("observation.images.image", "observation.images.image2"):
                row[key] = policy_image(row[key], self.runtime["observation_height"],
                                        self.runtime["observation_width"]).flip(-2, -1)
        return row


def adapt_dataset(dataset, source_manifest):
    from torch.utils.data import default_collate
    import torch
    sources = {s["repo_id"]: s for s in source_manifest["baseline_task_sources"]}
    expected_ids = source_manifest["repo_ids"]
    if list(dataset.repo_ids) != expected_ids or len(dataset) != source_manifest["dataset_size"]:
        raise ValueError("native dataset order or transition count differs from frozen sampler")
    runtime = source_manifest["baseline_runtime"]
    samples, checks = [], []
    for i, native in enumerate(dataset._datasets):
        repo_id = expected_ids[i]
        role = source_manifest["datasets"][repo_id]["role"]
        source = sources.get(repo_id)
        if (role in ("new", "old")) != (source is not None):
            raise ValueError("demonstration conversion missing or incorrectly applied to replay")
        if digest(Path(native.root) / "meta/info.json") != source_manifest["datasets"][repo_id]["info_sha256"]:
            raise ValueError("training source metadata changed")
        view = CoFTInputView(native, source, runtime)
        dataset._datasets[i] = view
        row = view[0]
        if row["action"].shape != (50, 7) or row["observation.state"].shape != (8,):
            raise ValueError("state/action training input shape mismatch")
        if not torch.isfinite(row["action"]).all() or not torch.isfinite(row["observation.state"]).all():
            raise ValueError("non-finite training input")
        samples.append({k: row[k] for k in ("observation.state", "observation.images.image",
                                           "observation.images.image2", "action", "action_is_pad", "task")})
        checks.append({"repo_id": repo_id, "role": role, "frames": len(native),
                       "state_conversion": "verified_demo_sidecar" if source else "native_v44_replay",
                       "image_shape": list(row["observation.images.image"].shape),
                       "fps": native.fps, "action_horizon": 50})
    mixed = default_collate(samples)
    if mixed["observation.images.image"].shape[1:] != (3, 128, 128):
        raise ValueError("mixed demonstration/replay camera contract mismatch")
    return dataset, checks


def main():
    cpu_environment()
    args = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--source_sampler_manifest=")]
    if len(args) != 1:
        raise ValueError("training needs one immutable source sampler manifest")
    path = Path(args[0])
    source = read_json(path)
    from .slow_loop_expansion import verify_reference_sources, require_selected_gpu
    verify_reference_sources()
    require_selected_gpu(source["baseline_gpu_index"])
    from .references.slow_loop_main_20260914 import training, coft_recovery
    from lerobot.policies.pi05.configuration_pi05 import PI05Config  # register before native CLI parsing
    # These aliases exist only in this newly launched baseline process.
    sys.modules["mode_gate.training"] = training
    sys.modules["mode_gate.coft_recovery"] = coft_recovery
    from .references.slow_loop_main_20260914 import native_lerobot_train as native
    make_policy = native.make_policy
    def recorded_policy(*args, **kwargs):
        from .references.slow_loop_main_20260914.checkpoint_math import parameter_group
        policy = make_policy(*args, **kwargs)
        counts = {group: 0 for group in ("vision", "language", "action")}
        for name, parameter in policy.named_parameters():
            if parameter.requires_grad:
                counts[parameter_group(name)] += parameter.numel()
        if any(count == 0 for count in counts.values()):
            raise ValueError("main slow-loop baseline requires trainable vision, language and action parameters")
        write_json(path.parent / "training_policy.json", {"full_policy_sft": True,
                   "trainable_parameters_by_group": counts,
                   "total_parameters": sum(p.numel() for p in policy.parameters()),
                   "parent_checkpoint": str(policy.config.pretrained_path)})
        return policy
    native.make_policy = recorded_policy
    make_dataset = native.make_dataset
    def corrected_dataset(cfg):
        dataset, checks = adapt_dataset(make_dataset(cfg), source)
        write_json(path.parent / "input_validation.json", {"passed": True, "sources": checks,
                   "source_manifest_sha256": digest(path), "native_trainer": True})
        return dataset
    native.make_dataset = corrected_dataset
    update = native.update_policy
    progress_path = path.parent / "training_progress.json"
    def report_update(*args, **kwargs):
        metrics, values = update(*args, **kwargs)
        accelerator = kwargs.get("accelerator")
        if accelerator.sync_gradients:
            import math
            loss, norm = float(metrics.loss.val), float(metrics.grad_norm.val)
            if not math.isfinite(loss) or not math.isfinite(norm):
                raise FloatingPointError("non-finite native trainer loss/gradient")
            step = int(metrics.steps) + 1
            if step == 1 or step % 20 == 0:
                write_json(progress_path, {"phase": "full_policy_sft", "step": step,
                           "target_steps": 1000, "loss": loss, "grad_norm": norm,
                           "learning_rate": float(metrics.lr.val), "batch_size": 4,
                           "gradient_accumulation_steps": 8, "global_batch_size": 32,
                           "pid": os.getpid()})
        return metrics, values
    native.update_policy = report_update
    native.main()


if __name__ == "__main__":
    main()
