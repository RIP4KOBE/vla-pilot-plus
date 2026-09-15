"""CPU canary for the threshold-free Grounded Capability Verifier."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from mode_gate.io_utils import atomic_write_json, sha256_file
from mode_gate.types import ControllerRoute
from mode_gate.verifier import (
    DeployedVerifierPredictor,
    CandidateVerifierInput,
    PlattCalibrator,
    save_verifier_input,
)
from mode_gate.verifier_training import (
    VerifierExample,
    VerifierTrainingConfig,
    train_verifier,
)


def _input(value: float) -> CandidateVerifierInput:
    return CandidateVerifierInput(
        scene_feature=np.full(2048, value, dtype=np.float32),
        candidate_trajectories=np.full((2, 11, 15), value, dtype=np.float32),
        executed_history=np.zeros((0, 15), dtype=np.float32),
        remaining_budget=50, retry_budget=50, candidate_ids=("c0", "c1"),
        backbone_id="synthetic-v44-canary-not-for-deployment",
    )


def run(output_root: Path) -> dict[str, object]:
    output_root = Path(output_root).resolve()
    feature_root = output_root / "features"
    examples: list[VerifierExample] = []
    items: list[CandidateVerifierInput] = []
    splits = ("train",) * 8 + ("test",) * 4
    for index, split in enumerate(splits):
        expansion = bool(index % 2)
        item = _input(float(expansion) + index * 0.001)
        items.append(item)
        feature_path = feature_root / f"context-{index:02d}.npz"
        save_verifier_input(
            feature_path,
            item,
            metadata={"policy_id": "policy_canary", "split": split},
        )
        examples.append(
            VerifierExample(
                record_id=f"context-{index:02d}",
                policy_id="policy_canary",
                group_id=f"group-{index:02d}",
                split=split,
                feature_path=str(feature_path),
                source="audit",
                target_class=int(expansion), annotation_id=f"synthetic-{index}",
                feature_sha256=sha256_file(feature_path),
                episode_id=f"synthetic-episode-{index}", snapshot_hash=f"snapshot-{index}",
                weight=1.0,
            )
        )

    result = train_verifier(
        examples,
        policy_id="policy_canary",
        output_root=output_root / "artifacts",
        config=VerifierTrainingConfig(
            seed=20260827,
            max_epochs=12,
            patience=4,
            batch_size=4,
            device="cpu",
        ),
    )
    artifact = Path(result.artifact_root)
    manifest = json.loads((artifact / "manifest.json").read_text(encoding="utf-8"))
    if "threshold" in manifest or manifest.get("decision_rule") != "head_argmax":
        raise RuntimeError("verifier artifact retained a hand-set routing threshold")

    predictor = DeployedVerifierPredictor(artifact)
    first = predictor.predict(items[-1])
    expected = (
        ControllerRoute.EXPAND
        if first.logits[1] > first.logits[0]
        else ControllerRoute.RESTEER
    )
    if first.route is not expected:
        raise RuntimeError("deployed route differs from output-head argmax")

    # Force the diagnostic probability to contradict the head decision.  The
    # route must remain unchanged, proving calibration is not a hidden gate.
    predictor.calibrator = PlattCalibrator(
        0.0,
        100.0 if first.route is ControllerRoute.RESTEER else -100.0,
    )
    contradictory = predictor.predict(items[-1])
    if contradictory.route is not first.route:
        raise RuntimeError("diagnostic probability changed the direct head route")

    report = {
        "schema_version": "verifier-head-argmax-canary-v1",
        "policy_id": "policy_canary",
        "verifier_id": result.verifier_id,
        "artifact_root": str(artifact),
        "artifact_schema": manifest["schema_version"],
        "decision_rule": manifest["decision_rule"],
        "threshold_present": "threshold" in manifest,
        "route": first.route.value,
        "logits": list(first.logits),
        "calibrated_p_expansion": first.p_expansion,
        "contradictory_diagnostic_p_expansion": contradictory.p_expansion,
        "route_unchanged_under_contradictory_probability": True,
        "best_epoch": result.best_epoch,
        "deployment_gate_passed": result.gate.passed,
        "deployment_gate_reasons": list(result.gate.reasons),
    }
    atomic_write_json(output_root / "canary_report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.output_root), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
