"""Read-only views of the existing forty-cell protocol; no final-seal opening."""
import hashlib
import json
import random
from pathlib import Path

from .io import read_json

TRAIN_SPLIT = "demo_online_pool"
EVAL_SPLITS = ("fixed_development_probe", "policy_alpha_selection", "policy_regression")


class Protocol:
    def __init__(self, path):
        self.path = Path(path).resolve()
        manifest = read_json(path)
        unsigned = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if actual != manifest.get("manifest_sha256"):
            raise ValueError("joint protocol checksum mismatch")
        self.digest = actual
        self.tasks = {v["task_key"]: v for v in manifest["tasks"]}
        if len(self.tasks) != 40:
            raise ValueError("expected the project's forty LIBERO-PRO cells")
        for task in self.tasks.values():
            if task["benchmark"] != "LIBERO-PRO" or task["perturbation_variant"] == "base":
                raise ValueError("unperturbed LIBERO is not an evaluation target")
            groups = list(task["splits"].values())
            flat = [str(s) for group in groups for s in group]
            if len(flat) != len(set(flat)):
                raise ValueError("overlapping protocol state shards")

    def order(self, seed):
        keys = sorted(self.tasks)
        random.Random(seed).shuffle(keys)
        return keys

    def contexts(self, split, seed, task_keys=None):
        if split not in (TRAIN_SPLIT, *EVAL_SPLITS):
            raise ValueError("baseline CLI only exposes demo/online and development policy shards")
        result = []
        for key in task_keys or self.order(seed):
            task = self.tasks[key]
            for state in task["splits"][split]:
                material = f"baseline-context-v1:{self.digest}:{seed}:{key}:{state}:{split}"
                number = int.from_bytes(hashlib.sha256(material.encode()).digest()[:4], "big")
                result.append({**{k: task[k] for k in ("task_key", "runtime_suite", "suite", "task_id", "task_index", "perturbation_variant")},
                               "init_state_id": int(state), "seed": number, "split": split})
        return result

    def validate_training_source(self, source):
        key = source["task_key"]
        if key not in self.tasks:
            raise ValueError(f"unknown task key: {key}")
        if source.get("split") != TRAIN_SPLIT:
            raise ValueError("new task demonstrations must declare split=demo_online_pool")
        ids = set(map(str, source.get("init_state_ids", [])))
        if not ids or not ids <= set(self.tasks[key]["splits"][TRAIN_SPLIT]):
            raise ValueError("demo provenance is absent or intersects held-out states")
