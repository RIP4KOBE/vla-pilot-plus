"""Blocking hgpu1 preflight for the mode-aware self-improvement loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Callable, Mapping

import numpy as np
import torch

from core.fkd_class import FKD

from .checkpoint_math import checkpoint_digest, partition_counts
from .config import ModeGateConfig
from .eval_manifest import validate_libero_pro_manifest
from .io_utils import atomic_write_json, sha256_file


SNAPSHOT_CANARY_SOURCE_PATHS = (
    "core/env_adapters/libero_adapter.py",
    "core/pi05_steer.py",
    "mode_gate/scene_encoder.py",
    "mode_gate/eval_manifest.py",
    "mode_gate/snapshots.py",
    "patches/robosuite_egl.py",
    "scripts/libero_snapshot_canary.py",
    "third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py",
)

TRAINING_SMOKE_SOURCE_PATHS = (
    "mode_gate/training.py",
    "mode_gate/checkpoint_math.py",
    "scripts/training_smoke.py",
    "third_party/lerobot/src/lerobot/configs/train.py",
    "third_party/lerobot/src/lerobot/scripts/lerobot_train.py",
    "third_party/lerobot/src/lerobot/policies/pi05/modeling_pi05.py",
)

GEMINI_CANARY_SOURCE_PATHS = (
    "configs/perception.yaml",
    "core/gemini_grounder.py",
    "mode_gate/semantic_planner.py",
    "mode_gate/tickets.py",
    "scripts/gemini_canary.py",
)

TELEOP_CANARY_SOURCE_PATHS = (
    "core/env_adapters/libero_adapter.py",
    "mode_gate/data_pipeline.py",
    "mode_gate/teleop.py",
    "mode_gate/eval_manifest.py",
    "patches/robosuite_egl.py",
    "scripts/teleop_canary.py",
    "scripts/teleop_server.py",
)


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    passed: bool
    details: dict
    error: str | None = None


def run_preflight(
    *,
    repo_root: Path,
    output_path: Path,
    curriculum_manifest: Path | None = None,
    protocol_manifest: Path | None = None,
    snapshot_canary_result: Path | None = None,
    nccl_canary_result: Path | None = None,
    training_smoke_result: Path | None = None,
    gemini_canary_result: Path | None = None,
    teleop_canary_result: Path | None = None,
    baseline_manifest: Path | None = None,
    run_tests: bool = True,
    require_hgpu1_layout: bool = True,
) -> dict:
    repo_root = Path(repo_root).resolve()
    checks: list[PreflightCheck] = []

    def check(name: str, fn: Callable[[], dict]) -> None:
        try:
            checks.append(PreflightCheck(name, True, fn()))
        except Exception as exc:
            checks.append(
                PreflightCheck(name, False, {}, f"{type(exc).__name__}: {exc}")
            )

    check("server_layout", lambda: _server_layout(repo_root, require_hgpu1_layout))
    check("cuda_inventory", _cuda_inventory)
    check("python_dependencies", _python_dependencies)
    check("mode_gate_config", _mode_gate_config)
    check("theta0_checkpoint", _theta0_checkpoint)
    check("persistent_storage", _persistent_storage)
    check("egl_render", _egl_render)
    check(
        "frozen_perception_assets",
        lambda: _perception_checkpoint_inventory(repo_root),
    )
    check("fkd_real_resample", _fkd_real_resample)
    check("lerobot_training_contract", _lerobot_training_contract)
    if run_tests:
        check("pytest_suite", lambda: _pytest_suite(repo_root))
    if snapshot_canary_result is not None:
        check(
            "libero_snapshot_policy_scene_canary",
            lambda: _snapshot_canary(
                Path(snapshot_canary_result),
                repo_root,
                Path(protocol_manifest) if protocol_manifest is not None else None,
            ),
        )
    if protocol_manifest is not None:
        check(
            "joint_protocol_manifest",
            lambda: _protocol_manifest(Path(protocol_manifest)),
        )
    if curriculum_manifest is not None:
        if protocol_manifest is None:
            raise ValueError("curriculum preflight requires the joint protocol")
        check(
            "libero_pro_resource_manifest",
            lambda: _curriculum_manifest(
                Path(curriculum_manifest),
                Path(protocol_manifest),
                repo_root,
            ),
        )
    if baseline_manifest is not None:
        check(
            "baseline_protocol_manifest",
            lambda: _baseline_manifest(
                Path(baseline_manifest), Path(protocol_manifest)
            ),
        )
    if nccl_canary_result is not None:
        check(
            "two_gpu_nccl_canary",
            lambda: _nccl_canary(Path(nccl_canary_result), repo_root),
        )
    if training_smoke_result is not None:
        check(
            "bounded_gpu_training_smoke",
            lambda: _training_smoke(Path(training_smoke_result), repo_root),
        )
    if gemini_canary_result is not None:
        check(
            "gemini_provider_canary",
            lambda: _gemini_canary(Path(gemini_canary_result), repo_root),
        )
    if teleop_canary_result is not None:
        check(
            "t2_teleop_canary",
            lambda: _teleop_canary(
                Path(teleop_canary_result),
                repo_root,
                Path(protocol_manifest) if protocol_manifest is not None else None,
            ),
        )
    result = {
        "schema_version": "hgpu1-preflight-v1",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "host": socket.gethostname(),
        "repo_root": str(repo_root),
        "python": platform.python_version(),
        "git_revision": _git_revision(repo_root),
        "passed": all(item.passed for item in checks),
        "checks": [asdict(item) for item in checks],
    }
    atomic_write_json(Path(output_path), result)
    if not result["passed"]:
        failed = [item.name for item in checks if not item.passed]
        raise RuntimeError(f"blocking preflight checks failed: {failed}")
    return result


def _server_layout(repo_root: Path, required: bool) -> dict:
    expected = Path("/shared/hengyil6/vls/repo")
    same_target = expected.exists() and repo_root.exists() and expected.samefile(repo_root)
    if required and not same_target:
        raise ValueError(f"delivery root must be {expected}, got {repo_root}")
    return {
        "delivery_alias": str(expected),
        "physical_target": str(repo_root),
        "same_filesystem_target": same_target,
    }


def _cuda_inventory() -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    count = torch.cuda.device_count()
    names = [torch.cuda.get_device_name(index) for index in range(count)]
    memory = [torch.cuda.get_device_properties(index).total_memory for index in range(count)]
    if count != 8 or any("RTX 6000D" not in name for name in names):
        raise RuntimeError(f"expected 8x RTX 6000D, got {names}")
    return {"count": count, "names": names, "total_memory_bytes": memory}


def _python_dependencies() -> dict:
    required = {
        "fastapi": "0.116.1",
        "uvicorn": "0.35.0",
        "h5py": None,
        "scikit-learn": None,
        "safetensors": None,
        "torch": None,
    }
    versions = {name: importlib.metadata.version(name) for name in required}
    mismatches = {
        name: (versions[name], expected)
        for name, expected in required.items()
        if expected is not None and versions[name] != expected
    }
    if mismatches:
        raise RuntimeError(f"dependency version mismatch: {mismatches}")
    return versions


def _mode_gate_config() -> dict:
    config = ModeGateConfig()
    config.validate()
    if config.chunk_horizon != 10 or config.retry_budget != 4:
        raise RuntimeError("controller horizon/budget contract changed")
    return {
        "sample_count": config.sample_count,
        "chunk_horizon": config.chunk_horizon,
        "retry_budget": config.retry_budget,
        "verifier_decision_rule": "head_argmax",
    }


def _theta0_checkpoint() -> dict:
    path = Path(ModeGateConfig().theta0_checkpoint)
    counts = partition_counts(path)
    if sum(counts.values()) != 812:
        raise RuntimeError(f"theta0 tensor count changed: {counts}")
    expected = {"vision": 439, "language": 164, "action": 209}
    if counts != expected:
        raise RuntimeError(f"theta0 partition changed: expected={expected}, got={counts}")
    return {
        "path": str(path),
        "bytes": sum(item.stat().st_size for item in path.glob("*.safetensors")),
        "digest": checkpoint_digest(path),
        "partition": counts,
    }


def _persistent_storage() -> dict:
    config = ModeGateConfig()
    roots = [
        Path(config.registry_root),
        Path(config.incident_root),
        Path(config.snapshot_root),
        Path(config.slow_loop_root),
    ]
    for root in roots:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / f".preflight-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        if probe.read_text(encoding="utf-8") != "ok":
            raise OSError(f"storage readback failed: {root}")
        probe.unlink()
    stat = os.statvfs("/shared")
    return {
        "roots": [str(root) for root in roots],
        "shared_free_bytes": stat.f_bavail * stat.f_frsize,
    }


def _egl_render() -> dict:
    os.environ["PYOPENGL_PLATFORM"] = "egl"
    os.environ["MUJOCO_GL"] = "egl"
    import mujoco

    model = mujoco.MjModel.from_xml_string(
        "<mujoco><worldbody><light pos='0 0 2'/><geom type='sphere' size='.1'/></worldbody></mujoco>"
    )
    data = mujoco.MjData(model)
    renderer = mujoco.Renderer(model, height=64, width=64)
    try:
        renderer.update_scene(data)
        image = renderer.render()
    finally:
        renderer.close()
    if image.shape != (64, 64, 3) or not np.isfinite(image).all():
        raise RuntimeError("EGL render returned an invalid frame")
    return {"shape": list(image.shape), "mean_pixel": float(image.mean())}


def _fkd_real_resample() -> dict:
    torch.manual_seed(8)
    fkd = FKD(
        potential_type="rt",
        lmbda=100.0,
        num_particles=40,
        adaptive_resampling=False,
        resample_frequency=1,
        resampling_t_start=0,
        resampling_t_end=1,
        timesteps=[0, 1],
        reward_fn=lambda value: value[:, 0],
        device="cpu",
    )
    particles = torch.zeros(40, 1)
    particles[0, 0] = 1.0
    fkd.resample(sampling_idx=0, latents=particles, x0_preds=particles)
    diagnostics = fkd.diagnostics()
    if not diagnostics["resample_indices"] or diagnostics["unique_ratio"] >= 1.0:
        raise RuntimeError("synthetic FKD preflight did not perform a real resample")
    return diagnostics


def _lerobot_training_contract() -> dict:
    from lerobot.configs.train import TrainPipelineConfig
    from lerobot.optim.schedulers import CosineDecayWithWarmupSchedulerConfig
    from lerobot.policies.pi05.configuration_pi05 import PI05Config

    fields = TrainPipelineConfig.__dataclass_fields__
    required = {
        "freeze_pretrained_processor_stats",
        "gradient_accumulation_steps",
        "source_sampler_manifest",
        "tokenizer_path",
        "save_final_params_only",
    }
    if not required.issubset(fields):
        raise RuntimeError(f"LeRobot trainer is missing fields {sorted(required - set(fields))}")
    if "auto_scale" not in CosineDecayWithWarmupSchedulerConfig.__dataclass_fields__:
        raise RuntimeError("scheduler auto_scale switch is missing")
    if "scheduler_auto_scale" not in PI05Config.__dataclass_fields__:
        raise RuntimeError("PI05 scheduler_auto_scale switch is missing")
    return {
        "processor_stats_freeze": True,
        "source_sampler": True,
        "local_tokenizer": True,
        "final_params_only": True,
        "scheduler_auto_scale_switch": True,
    }


def _protocol_manifest(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_libero_pro_manifest(value)
    expected_variants = {
        "use_object": 10,
        "use_swap": 10,
        "use_language": 10,
        "use_environment": 10,
    }
    variant_counts = {
        variant: sum(
            str(task.get("perturbation_variant")) == variant
            for task in value["tasks"]
        )
        for variant in expected_variants
    }
    return {
        "path": str(path),
        "manifest_sha256": value["manifest_sha256"],
        "tasks": len(value["tasks"]),
        "benchmark": "LIBERO-PRO",
        "variant_counts": variant_counts,
    }


def _curriculum_manifest(
    path: Path,
    protocol_path: Path,
    repo_root: Path,
) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "libero40-curriculum-v1":
        raise ValueError("unsupported curriculum manifest schema")
    claimed = str(value.get("manifest_sha256", ""))
    payload = {key: item for key, item in value.items() if key != "manifest_sha256"}
    import hashlib

    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if claimed != actual or protocol.get("dataset_hash") != claimed:
        raise ValueError("curriculum hash or joint-protocol binding is invalid")
    tasks = list(value.get("tasks", ()))
    if len(tasks) != 40 or value.get("benchmark") != "LIBERO-PRO":
        raise ValueError("curriculum is not the formal LIBERO-PRO 40-cell catalog")
    protocol_keys = {
        (str(task["suite"]), str(task["task_id"]), str(task["perturbation_variant"]))
        for task in protocol["tasks"]
    }
    resource_keys = set()
    for task in tasks:
        key = (
            str(task["suite"]),
            str(task["task_id"]),
            str(task["perturbation_variant"]),
        )
        resource_keys.add(key)
        if (
            task.get("benchmark") != "LIBERO-PRO"
            or task.get("runtime_suite") == task.get("suite")
        ):
            raise ValueError(f"curriculum has an unperturbed task: {key}")
        for path_field, digest_field in (
            ("bddl_file", "bddl_sha256"),
            ("init_state_file", "init_state_sha256"),
        ):
            resource = (repo_root / str(task[path_field])).resolve()
            if not resource.is_relative_to(repo_root) or not resource.is_file():
                raise FileNotFoundError(resource)
            if sha256_file(resource) != str(task[digest_field]):
                raise ValueError(f"curriculum resource hash changed: {resource}")
        init_path = (repo_root / str(task["init_state_file"])).resolve()
        states = torch.load(init_path, map_location="cpu", weights_only=False)  # nosec B614
        if len(states) != 50:
            raise ValueError(f"curriculum init-state count changed: {init_path}")
    if resource_keys != protocol_keys:
        raise ValueError("curriculum task cells differ from the joint protocol")
    return {
        "path": str(path),
        "manifest_sha256": claimed,
        "task_count": len(tasks),
        "benchmark": "LIBERO-PRO",
        "resources_verified": len(tasks) * 2,
    }


def snapshot_canary_source_fingerprint(repo_root: Path) -> str:
    """Hash the exact source surface exercised by the real snapshot canary."""

    return _source_fingerprint(repo_root, SNAPSHOT_CANARY_SOURCE_PATHS)


def training_smoke_source_fingerprint(repo_root: Path) -> str:
    return _source_fingerprint(repo_root, TRAINING_SMOKE_SOURCE_PATHS)


def gemini_canary_source_fingerprint(repo_root: Path) -> str:
    return _source_fingerprint(repo_root, GEMINI_CANARY_SOURCE_PATHS)


def teleop_canary_source_fingerprint(repo_root: Path) -> str:
    return _source_fingerprint(repo_root, TELEOP_CANARY_SOURCE_PATHS)


def _source_fingerprint(repo_root: Path, paths: tuple[str, ...]) -> str:
    digest = hashlib.sha256()
    for relative in paths:
        path = Path(repo_root) / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _directory_fingerprint(root: Path) -> str:
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if (
            any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts)
            or path.suffix in {".pyc", ".pyo"}
        ):
            continue
        files.append(path)
    for path in sorted(files):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    if not files:
        raise ValueError(f"frozen source directory is empty: {root}")
    return digest.hexdigest()


def _perception_checkpoint_inventory(repo_root: Path) -> dict:
    from omegaconf import OmegaConf

    manifest_path = Path(repo_root) / "configs" / "perception_assets.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "vls-perception-assets-v1":
        raise ValueError("invalid perception asset manifest schema")
    dino = manifest.get("dinov2")
    if not isinstance(dino, dict) or dino.get("model") != "dinov2_vitb14":
        raise ValueError("perception manifest must freeze dinov2_vitb14")

    repo_path = Path(str(dino["repo_path"])).resolve()
    weights_path = Path(str(dino["weights_path"])).resolve()
    if not (repo_path / "hubconf.py").is_file():
        raise FileNotFoundError(f"frozen DINOv2 source is missing: {repo_path}")
    if not weights_path.is_file():
        raise FileNotFoundError(f"frozen DINOv2 weights are missing: {weights_path}")

    perception = OmegaConf.load(Path(repo_root) / "configs" / "perception.yaml")
    keypoints = perception.keypoint_detector
    if (
        str(keypoints.feature_extractor) != dino["model"]
        or Path(str(keypoints.dinov2_repo_path)).resolve() != repo_path
        or Path(str(keypoints.dinov2_weights_path)).resolve() != weights_path
    ):
        raise ValueError("perception config differs from the frozen asset manifest")

    source_fingerprint = _directory_fingerprint(repo_path)
    weights_sha256 = sha256_file(weights_path)
    if source_fingerprint != dino.get("repo_sha256"):
        raise ValueError("frozen DINOv2 source fingerprint changed")
    if weights_sha256 != dino.get("weights_sha256"):
        raise ValueError("frozen DINOv2 weights checksum changed")
    if weights_path.stat().st_size != int(dino.get("weights_bytes", -1)):
        raise ValueError("frozen DINOv2 weights size changed")

    state_dict = torch.load(
        weights_path,
        map_location="cpu",
        weights_only=True,
        mmap=True,
    )
    if not isinstance(state_dict, dict) or len(state_dict) != int(
        dino.get("state_dict_keys", -1)
    ):
        raise ValueError("frozen DINOv2 state dict is invalid")
    return {
        "manifest": str(manifest_path),
        "model": dino["model"],
        "repo_path": str(repo_path),
        "repo_sha256": source_fingerprint,
        "weights_path": str(weights_path),
        "weights_sha256": weights_sha256,
        "weights_bytes": weights_path.stat().st_size,
        "state_dict_keys": len(state_dict),
        "runtime_downloads": False,
    }


def _pytest_suite(repo_root: Path) -> dict:
    environment = os.environ.copy()
    existing = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        f"{repo_root}{os.pathsep}{existing}" if existing else str(repo_root)
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(repo_root / "tests")],
        cwd=repo_root,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=300,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "pytest failed: " + "\n".join(completed.stdout.splitlines()[-20:])
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return {"returncode": 0, "summary": lines[-1] if lines else "passed"}


def _nccl_canary(path: Path, repo_root: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not value.get("passed") or int(value.get("world_size", -1)) != 2:
        raise RuntimeError("2-GPU NCCL canary has not passed")
    expected_script = _source_fingerprint(repo_root, ("scripts/nccl_canary.py",))
    if value.get("source_fingerprint") != expected_script:
        raise RuntimeError("NCCL canary is stale for the current source")
    return value


def _training_smoke(path: Path, repo_root: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("source_fingerprint") != training_smoke_source_fingerprint(repo_root):
        raise RuntimeError("training smoke is stale for the current trainer source")
    if not value.get("passed") or int(value.get("returncode", -1)) != 0:
        reason = value.get("blocked_reason") or value.get("log_path") or "unknown"
        raise RuntimeError(
            f"bounded-GPU training smoke has not passed: {reason}"
        )
    selected = value.get("selected_gpu_indices") or ()
    requested = int(value.get("requested_gpu_count", -1))
    if not 1 <= requested <= 2 or len(selected) != requested:
        raise RuntimeError("training smoke did not stay within the pinned 1–2 GPU budget")
    if (
        int(value.get("per_device_batch_size", -1))
        * int(value.get("gradient_accumulation_steps", -1))
        * requested
        != 32
        or int(value.get("effective_global_batch_size", -1)) != 32
    ):
        raise RuntimeError("training smoke did not preserve effective global batch 32")
    if sum((value.get("partition_counts") or {}).values()) != 812:
        raise RuntimeError("training smoke checkpoint is incomplete")
    return {
        key: value.get(key)
        for key in (
            "recorded_at",
            "elapsed_seconds",
            "checkpoint",
            "partition_counts",
            "source_manifest_sha256",
            "source_fingerprint",
        )
    }


def _gemini_canary(path: Path, repo_root: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("source_fingerprint") != gemini_canary_source_fingerprint(repo_root):
        raise RuntimeError("Gemini canary is stale for the current provider source")
    if (
        value.get("schema_version") != "hgpu1-gemini-canary-v3"
        or value.get("visual_input_kind") != "synthetic"
        or not value.get("passed")
        or value.get("model") != "gemini-robotics-er-2-preview"
        or value.get("ticket_model") != "gemini-robotics-er-2-preview"
        or value.get("interaction_exercised") is not True
        or value.get("grounding_exercised") is not True
        or value.get("stage_exercised") is not True
        or value.get("ticket_exercised") is not True
    ):
        raise RuntimeError(f"Gemini provider canary has not passed: {value.get('error')}")
    return value


def _assert_libero_pro_canary_context(
    value: Mapping[str, object],
    protocol_path: Path | None,
) -> dict:
    context = value.get("context")
    if not isinstance(context, dict):
        raise RuntimeError("canary does not record its formal context")
    if (
        context.get("benchmark") != "LIBERO-PRO"
        or context.get("runtime_suite") == context.get("suite")
        or context.get("split") != "fixed_development_probe"
    ):
        raise RuntimeError(f"canary did not use a LIBERO-PRO development context: {context}")
    if protocol_path is not None:
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        if context.get("manifest_sha256") != protocol.get("manifest_sha256"):
            raise RuntimeError("canary is not bound to the current formal protocol")
    return context


def _teleop_canary(
    path: Path,
    repo_root: Path,
    protocol_path: Path | None = None,
) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("source_fingerprint") != teleop_canary_source_fingerprint(repo_root):
        raise RuntimeError("T2 teleop canary is stale for the current source")
    if not value.get("passed") or not value.get("localhost_only"):
        raise RuntimeError("real T2 teleoperation canary has not passed")
    _assert_libero_pro_canary_context(value, protocol_path)
    return value


def _baseline_manifest(path: Path, protocol_path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "baseline-suite-v1":
        raise ValueError("unsupported baseline manifest schema")
    if value.get("protocol_manifest_hash") != protocol.get("manifest_sha256"):
        raise ValueError("baseline manifest is not bound to the joint protocol")
    claimed = value.get("manifest_sha256")
    payload = {key: item for key, item in value.items() if key != "manifest_sha256"}
    import hashlib

    actual = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if claimed != actual:
        raise ValueError("baseline manifest checksum is invalid")
    ids = {str(item["id"]) for item in value.get("baselines", ())}
    required = {
        "fixed_budget_1",
        "fixed_budget_2",
        "fixed_budget_4",
        "fixed_budget_8",
        "fixed_budget_16",
        "fixed_budget_32",
        "always_expansion_retain",
        "oracle_verifier",
        "clare_minimal_faithful",
    }
    if not required.issubset(ids):
        raise ValueError(f"baseline manifest is incomplete: {sorted(required - ids)}")
    return {
        "path": str(path),
        "manifest_sha256": claimed,
        "protocol_manifest_hash": value["protocol_manifest_hash"],
        "baseline_count": len(value["baselines"]),
    }


def _snapshot_canary(
    path: Path,
    repo_root: Path,
    protocol_path: Path | None = None,
) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    simulator = value.get("simulator") or {}
    policy = value.get("policy") or {}
    scene = policy.get("scene_encoder") or {}
    expected_source = snapshot_canary_source_fingerprint(repo_root)
    if value.get("source_fingerprint") != expected_source:
        raise RuntimeError("snapshot canary is stale for the current source tree")
    if not value.get("passed") or not simulator.get("passed") or not policy.get("passed"):
        raise RuntimeError("real LIBERO snapshot/policy canary did not pass")
    if (
        simulator.get("snapshot_schema") != "decision-snapshot-v2"
        or simulator.get("model_body_pos_max_error") != 0.0
    ):
        raise RuntimeError("snapshot canary did not restore MuJoCo model-level state")
    if policy.get("first_action_max_error") != 0.0:
        raise RuntimeError("theta0 first-action replay is not exact")
    if policy.get("action_chunk_shape") != [1, 50, 7]:
        raise RuntimeError("theta0 action chunk contract changed")
    if not scene.get("passed") or scene.get("joint_shape") != [2048]:
        raise RuntimeError("theta0 scene encoder canary did not pass")
    context = _assert_libero_pro_canary_context(value, protocol_path)
    theta_digest = checkpoint_digest(Path(ModeGateConfig().theta0_checkpoint))
    if scene.get("theta0_digest") != theta_digest:
        raise RuntimeError("snapshot canary theta0 digest does not match the registry base")
    return {
        "path": str(path),
        "source_fingerprint": expected_source,
        "theta0_digest": theta_digest,
        "simulator_qpos_max_error": simulator.get("qpos_max_error"),
        "simulator_qvel_max_error": simulator.get("qvel_max_error"),
        "simulator_model_body_pos_max_error": simulator.get(
            "model_body_pos_max_error"
        ),
        "first_action_max_error": policy.get("first_action_max_error"),
        "scene_feature_id": scene.get("feature_id"),
        "context": context,
    }


def _git_revision(repo_root: Path) -> str:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
    ).strip()
    import hashlib

    digest = hashlib.sha256()
    roots = ("configs", "core", "mode_gate", "patches", "scripts", "tests", "utils")
    files = [repo_root / "main.py", repo_root / "requirements.txt"]
    for relative in roots:
        directory = repo_root / relative
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file())
    files.extend(
        repo_root / relative
        for relative in TRAINING_SMOKE_SOURCE_PATHS
        if relative.startswith("third_party/")
    )
    for path in sorted(set(files)):
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(repo_root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"{head}+source:{digest.hexdigest()}"


def source_revision(repo_root: Path) -> str:
    """Return the commit plus current tracked/untracked source fingerprint."""

    return _git_revision(Path(repo_root))


__all__ = [
    "PreflightCheck",
    "run_preflight",
    "gemini_canary_source_fingerprint",
    "snapshot_canary_source_fingerprint",
    "training_smoke_source_fingerprint",
    "source_revision",
]
