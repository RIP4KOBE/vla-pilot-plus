#!/usr/bin/env python3
"""Prepare steering assets without importing Torch, a simulator, or a model client.

From a new clone, install environment-steering.yml, then run::

    python scripts/prepare_steering_assets.py install-libero
    python scripts/prepare_steering_assets.py verify-rng
    python scripts/prepare_steering_assets.py configure --help

install-libero downloads the pinned public LIBERO-PRO revision, applies the
recorded vendor patch, and installs the small frozen object-swap input bundle.
It does not regenerate scenes. An existing verified local tree may instead be
copied with --source. Large models remain external and must be supplied as local
paths. configure writes a machine file and a LIBERO path file; neither contains
credentials. No command launches an episode or changes a Python environment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ASSET_MANIFEST = Path(__file__).with_name("steering_assets_manifest.json")
RNG_MANIFEST_SHA256 = "628c429d457def157c9163be94a1202721673f97f1e43aa6446e5a06889c6043"
SEEDS = [44, 235, 43, 546, 6, 621, 197, 87, 151, 548]


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def relative_file(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"Asset path must be relative: {name}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"Asset path escapes root: {name}")
    return target


def write_json(path: Path, value: dict, *, replace: bool = False) -> None:
    text = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text() != text and not replace:
        raise FileExistsError(f"Different file already exists: {path}; use --replace-config")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def verify_rng(root: Path) -> dict:
    manifest_path = root / "fixture-manifest.json"
    if digest(manifest_path) != RNG_MANIFEST_SHA256:
        raise ValueError("RNG manifest differs from the accepted initialization fixture")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != "episode_rng_fixture_manifest_v1" or manifest.get("calibration_valid") is not True:
        raise ValueError("RNG calibration is not valid")
    if digest(root / "audit.json") != manifest["calibration_audit_sha256"]:
        raise ValueError("RNG calibration audit hash differs")
    expected = {f"{task}:{phase}" for task in range(10) for phase in ("prepare", "rollout")}
    if set(manifest["fixtures"]) != expected:
        raise ValueError("Expected exactly twenty task/phase fixtures")
    for key, entry in manifest["fixtures"].items():
        task, phase = key.split(":")
        metadata = {"task_id": int(task), "episode_seed": SEEDS[int(task)], "phase": phase}
        if entry["metadata"] != metadata or digest(relative_file(root, entry["file"])) != entry["sha256"]:
            raise ValueError(f"RNG fixture identity/hash differs: {key}")
    return {"valid": True, "manifest": str(manifest_path.resolve()),
            "sha256": RNG_MANIFEST_SHA256, "fixture_count": 20,
            "scope": "file integrity only; RNG restoration is checked by the runtime hooks"}


def asset_manifest() -> dict:
    manifest = json.loads(ASSET_MANIFEST.read_text())
    for name in ("patch", "overlay"):
        path = relative_file(ASSET_MANIFEST.parent, manifest[name])
        if digest(path) != manifest[f"{name}_sha256"]:
            raise ValueError(f"Packaged LIBERO {name} hash differs")
    return manifest


def verify_libero(root: Path, manifest: dict | None = None) -> dict:
    manifest = manifest or asset_manifest()
    failures = []
    for name, expected in manifest["files"].items():
        path = relative_file(root, name)
        if not path.is_file() or digest(path) != expected:
            failures.append(name)
    if failures:
        raise ValueError("LIBERO missing/changed files: " + ", ".join(failures[:20]))
    return {"valid": True, "root": str(root.resolve()), "files_verified": len(manifest["files"]),
            "upstream_commit": manifest["upstream_commit"],
            "manifest_sha256": digest(ASSET_MANIFEST)}


def apply_libero_overlay(stage: Path, manifest: dict) -> None:
    # Bind the pre-normalization bytes: eight upstream files use CRLF.
    for name, expected in manifest["normalize_crlf_files"].items():
        path = relative_file(stage, name)
        if digest(path) != expected:
            raise ValueError(f"Upstream normalization input differs: {name}")
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    patch = str(relative_file(ASSET_MANIFEST.parent, manifest["patch"]))
    subprocess.run(["git", "-C", str(stage), "-c", "core.autocrlf=false", "apply", "--check", patch], check=True)
    subprocess.run(["git", "-C", str(stage), "-c", "core.autocrlf=false", "apply", patch], check=True)
    with zipfile.ZipFile(relative_file(ASSET_MANIFEST.parent, manifest["overlay"])) as archive:
        if sorted(archive.namelist()) != sorted(manifest["overlay_files"]):
            raise ValueError("Unexpected files in LIBERO overlay")
        for name in archive.namelist():
            target = relative_file(stage, name)
            if target.exists():
                raise FileExistsError(f"Frozen overlay would overwrite an upstream file: {name}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))


def install_libero(destination: Path, source: Path | None) -> dict:
    manifest = asset_manifest()
    if destination.exists():
        # Existing data is never overwritten, reset, or recursively deleted.
        return verify_libero(destination, manifest)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="steering-libero-", dir=destination.parent) as temporary:
        stage = Path(temporary) / "libero_pro"
        if source is not None:
            verify_libero(source, manifest)
            stage.mkdir()
            for name in manifest["files"]:
                target = relative_file(stage, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(relative_file(source, name), target)
        else:
            # Fetch the named commit including its blobs, avoiding partial-clone
            # lazy network access during asset verification or later execution.
            subprocess.run(["git", "init", "--quiet", str(stage)], check=True)
            subprocess.run(["git", "-C", str(stage), "remote", "add", "origin", manifest["upstream_url"]], check=True)
            subprocess.run(["git", "-C", str(stage), "fetch", "--depth=1", "origin", manifest["upstream_commit"]], check=True)
            subprocess.run(["git", "-C", str(stage), "-c", "core.autocrlf=false", "checkout", "--detach", manifest["upstream_commit"]], check=True)
            actual = subprocess.check_output(["git", "-C", str(stage), "rev-parse", "HEAD"], text=True).strip()
            if actual != manifest["upstream_commit"]:
                raise ValueError("Downloaded LIBERO commit differs")
            apply_libero_overlay(stage, manifest)
        result = verify_libero(stage, manifest)
        stage.rename(destination)
    result["root"] = str(destination.resolve())
    return result


def model_files(checkpoint: Path, text: Path, vision: Path, torch_home: Path) -> list[Path]:
    required = [checkpoint / "config.json", checkpoint / "ema/model.safetensors",
                text / "config.json", text / "spiece.model", text / "tokenizer_config.json",
                vision / "config.json", vision / "preprocessor_config.json", vision / "model.safetensors",
                torch_home / "hub/facebookresearch_dinov2_main/hubconf.py",
                torch_home / "hub/checkpoints/dinov2_vitb14_pretrain.pth"]
    text_weights = next((text / name for name in ("pytorch_model.bin", "model.safetensors") if (text / name).is_file()), None)
    if text_weights is None:
        raise FileNotFoundError("T5 snapshot must contain local model weights")
    required.append(text_weights)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Missing local model asset: {path}")
    # Cache roots select snapshots by mtime in the model loader: reject them here.
    if (text / "snapshots").is_dir() or (vision / "snapshots").is_dir():
        raise ValueError("Pass explicit encoder snapshot directories, not cache roots")
    config = json.loads((checkpoint / "config.json").read_text())
    if config.get("pred_horizon") != 64 or config.get("action_dim") != 128:
        raise ValueError("Unexpected RDT checkpoint dimensions")
    return required


def verify_libero_paths(local: dict) -> dict:
    """Bind the simulator's path configuration to the content-verified tree."""
    import yaml
    config_path = Path(local['libero_config']) / 'config.yaml'
    config = yaml.safe_load(config_path.read_text())
    benchmark = Path(local['libero_root']).resolve() / 'libero/libero'
    expected = {'benchmark_root': benchmark, 'assets': benchmark / 'assets',
                'bddl_files': benchmark / 'bddl_files', 'init_states': benchmark / 'init_files'}
    if not isinstance(config, dict):
        raise ValueError('LIBERO path config must be a mapping')
    for name, target in expected.items():
        value = config.get(name)
        if not isinstance(value, str) or not Path(value).is_absolute() or Path(value).resolve() != target.resolve():
            raise ValueError(f'LIBERO {name} does not point into the verified asset tree')
    return {'valid': True, 'config_path': str(config_path.resolve()), 'config_sha256': digest(config_path),
            'bindings': {name: str(path.resolve()) for name, path in expected.items()}}


def configure(args) -> dict:
    libero = args.libero_root.resolve()
    checked = verify_libero(libero)
    model_files(args.rdt_checkpoint, args.text_encoder, args.vision_encoder, args.torch_home)
    benchmark = libero / "libero/libero"
    paths = {"benchmark_root": str(benchmark), "assets": str(benchmark / "assets"),
             "bddl_files": str(benchmark / "bddl_files"), "init_states": str(benchmark / "init_files"),
             "datasets": str(libero / "libero/datasets")}
    # Offline evaluation does not require the demonstration dataset directory.
    local = {"gpu": args.gpu, "egl_device_id": args.egl_device_id,
             "allocator_limit_gib": args.allocator_limit_gib,
             "rdt_checkpoint": str(args.rdt_checkpoint.resolve()),
             "text_encoder": str(args.text_encoder.resolve()),
             "vision_encoder": str(args.vision_encoder.resolve()),
             "torch_home": str(args.torch_home.resolve()), "libero_root": str(libero),
             "libero_config": str(args.libero_config.resolve())}
    from scripts.steering_model_assets import verify_model_assets
    model_assets = verify_model_assets(local, repository_root=ROOT)
    write_json(args.libero_config / "config.yaml", paths, replace=args.replace_config)
    write_json(args.output, local, replace=args.replace_config)
    result = {"valid": True, "machine_config": str(args.output.resolve()), "libero": checked,
              "model_assets": model_assets,
              "gpu_egl_mapping": "supplied by caller; this CPU-only command does not validate hardware mapping"}
    if args.report:
        write_json(args.report, result, replace=args.replace_config)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    rng = commands.add_parser("verify-rng", help="Hash-check the twenty packaged RNG files; no Torch import")
    rng.add_argument("--root", type=Path, default=ROOT / "tests/fixtures/steering_rng")
    install = commands.add_parser("install-libero", help="Fetch pinned LIBERO or copy an already verified local tree")
    install.add_argument("--destination", type=Path, default=ROOT / "third_party/libero_pro")
    install.add_argument("--source", type=Path)
    verify = commands.add_parser("verify-libero", help="Check exact code, assets, and fixed object-swap inputs")
    verify.add_argument("--root", type=Path, default=ROOT / "third_party/libero_pro")
    config = commands.add_parser("configure", help="Write flat machine YAML (JSON syntax) and LIBERO path config")
    for name in ("rdt-checkpoint", "text-encoder", "vision-encoder", "torch-home"):
        config.add_argument("--" + name, type=Path, required=True)
    config.add_argument("--libero-root", type=Path, default=ROOT / "third_party/libero_pro")
    config.add_argument("--libero-config", type=Path, default=ROOT / ".libero_config")
    config.add_argument("--output", type=Path, required=True)
    config.add_argument("--gpu", type=int, required=True)
    config.add_argument("--egl-device-id", type=int, required=True, help="Host EGL index; do not infer it from the CUDA index")
    config.add_argument("--allocator-limit-gib", type=float, default=48)
    config.add_argument("--hash-weights", action="store_true", help="Compatibility option; full model content verification is now always required")
    config.add_argument("--report", type=Path)
    config.add_argument("--replace-config", action="store_true", help="Replace only the two explicitly named config files/report")
    args = parser.parse_args()
    if args.command == "verify-rng":
        result = verify_rng(args.root)
    elif args.command == "verify-libero":
        result = verify_libero(args.root)
    elif args.command == "install-libero":
        result = install_libero(args.destination.resolve(), args.source.resolve() if args.source else None)
    else:
        if args.gpu < 0 or args.egl_device_id < 0 or args.allocator_limit_gib <= 0:
            parser.error("GPU/EGL indices must be nonnegative and allocator limit positive")
        result = configure(args)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, KeyError) as error:
        print(f"Asset preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
