"""Local LeRobot demonstrations plus portable frozen-latent records."""
from pathlib import Path
import itertools

import torch
from torch.utils.data import DataLoader

from .io import read_json, write_json, load_tensors, save_tensors, to_cpu, digest


def load_task_sources(path, protocol):
    value = read_json(path)
    if value.get("schema_version") != "baseline-task-data-v1":
        raise ValueError("expected baseline-task-data-v1")
    sources = value["tasks"]
    if not sources:
        raise ValueError("no task demonstrations provided")
    seen = set()
    for source in sources:
        protocol.validate_training_source(source)
        if source["task_key"] in seen:
            raise ValueError("duplicate task source")
        seen.add(source["task_key"])
        if not Path(source["root"]).is_dir():
            raise FileNotFoundError(source["root"])
        if not (Path(source["root"]) / "meta/info.json").is_file():
            raise ValueError("source must be an existing local LeRobot dataset")
        if not source.get("episodes") or len(set(source["episodes"])) != len(source["episodes"]):
            raise ValueError("each task source must explicitly select unique episode indices")
    return sources


def demo_loader(source, runtime, batch_size, seed):
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
    info = read_json(Path(source["root"]) / "meta/info.json")
    fps = float(info["fps"])
    dataset = LeRobotDataset(repo_id=source["repo_id"], root=source["root"],
                            episodes=source.get("episodes"),
                            delta_timestamps={"action": [i / fps for i in range(50)]},
                            download_videos=False)
    from .demonstration_inputs import PolicyInputDataset
    dataset = PolicyInputDataset(dataset, source, runtime.cfg)
    if len(dataset) < batch_size:
        raise ValueError("demonstration dataset is smaller than one full microbatch")
    return DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0, drop_last=True,
                      generator=torch.Generator().manual_seed(seed))


def endless(loader):
    while True:
        yield from loader


def normalized_batch(runtime, raw):
    from .demonstration_inputs import checked_training_batch
    batch = runtime.preprocess(checked_training_batch(raw, runtime.cfg))
    return batch, batch["action"], raw.get("action_is_pad")


def cache_demonstrations(runtime, source, output, seed):
    """Disk cache contains no camera pixels; preserve exact token count and masks."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    index = []
    from .demonstration_inputs import CONTRACT
    loader = demo_loader(source, runtime, 1, seed)
    for i, raw in enumerate(loader):
        batch, actions, padding = normalized_batch(runtime, raw)
        embedded = runtime.embed(batch)
        item = {"embedded": to_cpu(embedded), "actions": to_cpu(actions),
                "padding": to_cpu(padding), "task_key": source["task_key"],
                "base_identity": runtime.identity["sha256"], "input_contract": CONTRACT,
                "source_conversion_sha256": source["policy_input"]["sha256"]}
        path = output / f"{i:08d}.pt"
        save_tensors(path, item)
        index.append({"path": str(path.resolve()), "bytes": path.stat().st_size,
                      "task_key": source["task_key"], "sha256": digest(path),
                      "base_identity": runtime.identity["sha256"], "input_contract": CONTRACT,
                      "source_conversion_sha256": source["policy_input"]["sha256"]})
        if i == 0 or (i + 1) % 250 == 0 or i + 1 == len(loader):
            write_json(output / "progress.json", {"records_completed": i + 1, "records_planned": len(loader),
                       "task_key": source["task_key"], "input_contract": CONTRACT})
    return index


def latent_batch(entries, device, base_identity):
    from .demonstration_inputs import CONTRACT
    records = []
    for item in entries:
        if item.get("input_contract") != CONTRACT:
            raise ValueError("latent cache uses an uncorrected demonstration input contract")
        if item["base_identity"] != base_identity or digest(item["path"]) != item["sha256"]:
            raise ValueError("latent cache belongs to another checkpoint or has changed")
        record = load_tensors(item["path"])
        if record.get("input_contract") != CONTRACT or record.get("source_conversion_sha256") != item.get("source_conversion_sha256"):
            raise ValueError("latent record input conversion differs from its index")
        if record["base_identity"] != base_identity or record["task_key"] != item["task_key"]:
            raise ValueError("latent record metadata differs from its index")
        records.append(record)
    embedded = {key: torch.cat([r["embedded"][key] for r in records]).to(device)
                for key in records[0]["embedded"]}
    actions = torch.cat([r["actions"] for r in records]).to(device)
    padding = torch.cat([r["padding"] if r["padding"] is not None else torch.zeros(1, 50, dtype=torch.bool)
                         for r in records]).to(device)
    return embedded, actions, padding, [r["task_key"] for r in records]
