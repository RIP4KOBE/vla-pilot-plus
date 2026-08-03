import csv
import json
import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.eds_mechanism_trace as trace_module
from core.eds_mechanism_trace import (
    EDSMechanismTrace,
    EDSParticleStage,
    save_mechanism_trace,
)


class _CustomPicklePayload:
    pass


def _legacy_tensor_payload():
    return {
        "metadata": {
            "suite": "libero_object_swap",
            "task_id": 0,
            "episode": 0,
            "global_step": 0,
            "reward_mode": "normal",
            "population_size": 1,
            "cem_iters": 1,
            "use_cem": False,
            "selected_idx": 0,
        },
        "keypoints": None,
        "scoring_keypoint_indices": None,
        "stages": [
            {
                "stage": "initial",
                "iter_idx": 0,
                "actions": torch.zeros(1, 64, 128),
                "trajectories": torch.zeros(1, 1, 3),
                "rewards": torch.zeros(1),
                "costs": torch.zeros(1),
                "parent_indices": None,
                "parent_ranks": None,
                "reward_before_rollout": None,
                "reward_after_rollout": None,
                "renoise_delta_norm": None,
                "rollout_delta_norm": None,
                "particle_sources": None,
            }
        ],
    }


def _stage() -> EDSParticleStage:
    return EDSParticleStage(
        stage="after_rollout",
        iter_idx=0,
        actions=torch.zeros(4, 64, 128),
        trajectories=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [0.1, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.2, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 0.0, 0.3]],
                [[0.0, 0.0, 0.0], [0.2, 0.2, 0.0]],
            ]
        ),
        rewards=torch.tensor([0.4, 0.3, 0.2, 0.1]),
        costs=torch.tensor([-0.4, -0.3, -0.2, -0.1]),
        parent_indices=torch.tensor([0, 1, 2, 3]),
        parent_ranks=torch.tensor([1, 2, 3, 4]),
        particle_sources=[
            "elite",
            "anchor_offspring",
            "weighted_offspring",
            "weighted_offspring",
        ],
        parent_probabilities=[None, None, 0.3, 0.2],
        parent_selection_kinds=[
            "deterministic_elite",
            "deterministic_anchor",
            "adaptive_ess",
            "adaptive_ess",
        ],
    )


def _trace() -> EDSMechanismTrace:
    return EDSMechanismTrace(
        suite="libero_object_swap",
        task_id=0,
        episode=0,
        global_step=8,
        reward_mode="normal",
        population_size=4,
        cem_iters=6,
        use_cem=False,
        keypoints=torch.tensor([[0.1, 0.2, 0.3]]),
        stages=[_stage()],
        selected_idx=0,
        selection_info={
            "enabled": True,
            "parent_weighting_mode": "adaptive_ess",
            "parent_coverage_mode": "eef_kcenter",
            "elite_survival_to_final_count": 1,
            "initial_anchor_lineage_count": 1,
            "final_unique_anchor_lineage_survival_count": 1,
            "final_unique_anchor_lineage_survival_ratio": 1.0,
            "per_iter": [
                {
                    "iter_idx": 0,
                    "selection_beta": 2.0,
                    "selection_ess": 2.0,
                    "selection_population_size": 4,
                    "selection_entropy_normalized": 0.75,
                    "selection_max_probability": 0.3,
                    "parent_indices": [0, 1, 2, 3],
                    "parent_ranks": [1, 2, 3, 4],
                    "parent_sources": [
                        "elite",
                        "anchor_offspring",
                        "weighted_offspring",
                        "weighted_offspring",
                    ],
                    "parent_probabilities": [None, None, 0.3, 0.2],
                    "parent_selection_kinds": [
                        "deterministic_elite",
                        "deterministic_anchor",
                        "adaptive_ess",
                        "adaptive_ess",
                    ],
                    "parent_count_by_source": {
                        "elite": 1,
                        "anchor_offspring": 1,
                        "weighted_offspring": 2,
                    },
                }
            ],
        },
        adaptive_rollout_info={
            "enabled": True,
            "per_iter": [
                {
                    "iter_idx": 0,
                    "diversity_reference": 0.4,
                    "diversity_current": 0.2,
                    "diversity_band_low": 0.3,
                    "diversity_band_high": 0.5,
                    "reward_confidence": 0.6,
                    "scale_requested": 10.0,
                    "scale_applied": 8.0,
                    "active_particle_count": 3,
                    "reason": "below_band",
                    "fallback_used": False,
                    "fallback_reason": None,
                }
            ],
        },
        chunk_memory_info={
            "enabled": True,
            "chunk_memory_available": True,
            "chunk_memory_used": True,
            "chunk_memory_candidate_count": 2,
            "chunk_memory_acceptance_ratio": 0.5,
            "chunk_memory_source_counts": {"fresh": 3, "memory": 1},
            "selected_chunk_population_source": "memory",
            "chunk_fresh_initial_best_reward": 0.2,
            "chunk_memory_initial_best_reward": 0.3,
            "chunk_fresh_initial_diversity": 0.1,
            "chunk_memory_initial_diversity": 0.2,
            "chunk_to_chunk_selected_trajectory_distance": 0.04,
        },
        search_schedule_info={
            "enabled": True,
            "search_schedule_mode": "adaptive",
            "eds_iters_executed": 4,
            "early_stop_used": True,
            "early_stop_reason": "adaptive_plateau_stable_in_band",
            "reward_plateau_count": 2,
            "stable_lineage_count": 2,
            "per_iter": [
                {
                    "iter_idx": 0,
                    "n_trunc_steps": 3,
                    "resolved_renoise_reason": "low_diversity",
                    "best_reward": 0.4,
                    "population_diversity": 0.2,
                    "diversity_band_low": 0.3,
                    "diversity_band_high": 0.5,
                    "best_lineage_stable": True,
                    "stable_lineage_count": 2,
                }
            ],
        },
        execution_info={
            "enabled": True,
            "execution_horizon_resolved": 4,
            "execution_horizon_reason": "near_target",
            "execution_horizon_stage_change": False,
            "replan_count": 3,
        },
    )


def _assert_json_safe(value):
    assert not torch.is_tensor(value)
    if isinstance(value, dict):
        for item in value.values():
            _assert_json_safe(item)
    elif isinstance(value, list):
        for item in value:
            _assert_json_safe(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_adaptive_trace_save_load_round_trip_preserves_small_metadata(tmp_path):
    trace = _trace()
    trace.adaptive_rollout_info["nonfinite_probe"] = float("nan")
    save_mechanism_trace(tmp_path, trace, save_tensors=True)

    metadata = json.loads((tmp_path / "first_chunk_metadata.json").read_text())
    payload = torch.load(
        tmp_path / "tensors" / "mechanism_trace.pt",
        weights_only=False,
    )
    _assert_json_safe(metadata)
    _assert_json_safe(payload["metadata"])
    assert metadata["adaptive_rollout_info"]["nonfinite_probe"] is None
    assert payload["selection_info"] == metadata["selection_info"]
    assert payload["execution_info"] == metadata["execution_info"]

    load_trace = getattr(trace_module, "load_mechanism_trace", None)
    assert callable(load_trace)
    restored = load_trace(tmp_path)
    assert restored.selection_info == metadata["selection_info"]
    assert restored.selection_info["initial_anchor_lineage_count"] == 1
    assert restored.selection_info["final_unique_anchor_lineage_survival_count"] == 1
    assert restored.selection_info["final_unique_anchor_lineage_survival_ratio"] == 1.0
    assert restored.adaptive_rollout_info == metadata["adaptive_rollout_info"]
    assert restored.chunk_memory_info == metadata["chunk_memory_info"]
    assert restored.search_schedule_info == metadata["search_schedule_info"]
    assert restored.execution_info == metadata["execution_info"]
    assert restored.stages[0].parent_probabilities == [None, None, 0.3, 0.2]
    assert restored.stages[0].parent_selection_kinds[1] == "deterministic_anchor"


def test_parent_csv_records_real_probability_and_deterministic_selection_kind(tmp_path):
    save_mechanism_trace(tmp_path, _trace(), save_tensors=True)

    with (tmp_path / "single_step_inner_loop" / "single_step_particles.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["parent_probability"] == ""
    assert rows[0]["parent_selection_kind"] == "deterministic_elite"
    assert rows[1]["parent_probability"] == ""
    assert rows[1]["parent_selection_kind"] == "deterministic_anchor"
    assert float(rows[2]["parent_probability"]) == 0.3
    assert rows[2]["parent_selection_kind"] == "adaptive_ess"


def test_legacy_trace_defaults_are_empty_and_loadable(tmp_path):
    trace = EDSMechanismTrace(
        suite=None,
        task_id=None,
        episode=None,
        global_step=0,
        reward_mode="normal",
        population_size=0,
        cem_iters=0,
        use_cem=False,
        keypoints=None,
    )
    save_mechanism_trace(tmp_path, trace, save_tensors=True)
    restored = trace_module.load_mechanism_trace(tmp_path)

    assert restored.selection_info == {}
    assert restored.adaptive_rollout_info == {}
    assert restored.chunk_memory_info == {}
    assert restored.search_schedule_info == {}
    assert restored.execution_info == {}
    assert restored.stages == []


def test_load_mechanism_trace_requests_weights_only(tmp_path, monkeypatch):
    tensor_path = tmp_path / "mechanism_trace.pt"
    torch.save(_legacy_tensor_payload(), tensor_path)
    real_load = torch.load
    calls = []

    def recording_load(*args, **kwargs):
        calls.append(dict(kwargs))
        return real_load(*args, **kwargs)

    monkeypatch.setattr(trace_module.torch, "load", recording_load)

    trace_module.load_mechanism_trace(tensor_path)

    assert calls == [{"map_location": "cpu", "weights_only": True}]


@pytest.mark.parametrize(
    "mutation",
    [
        "payload_not_dict",
        "metadata_not_dict",
        "stages_not_list",
        "missing_stage_costs",
        "stage_actions_not_tensor",
        "particle_sources_not_list",
        "parent_probabilities_bad_item",
    ],
)
def test_load_mechanism_trace_rejects_invalid_payload_structure(tmp_path, mutation):
    payload = _legacy_tensor_payload()
    if mutation == "payload_not_dict":
        payload = []
    elif mutation == "metadata_not_dict":
        payload["metadata"] = []
    elif mutation == "stages_not_list":
        payload["stages"] = {}
    elif mutation == "missing_stage_costs":
        del payload["stages"][0]["costs"]
    elif mutation == "stage_actions_not_tensor":
        payload["stages"][0]["actions"] = []
    elif mutation == "particle_sources_not_list":
        payload["stages"][0]["particle_sources"] = torch.tensor([1])
    else:
        payload["stages"][0]["parent_probabilities"] = ["bad"]
    tensor_path = tmp_path / f"{mutation}.pt"
    torch.save(payload, tensor_path)

    with pytest.raises(ValueError, match="mechanism trace"):
        trace_module.load_mechanism_trace(tensor_path)


def test_load_mechanism_trace_rejects_custom_pickle_payload(tmp_path):
    tensor_path = tmp_path / "custom_pickle.pt"
    torch.save(_CustomPicklePayload(), tensor_path)

    with pytest.raises(ValueError, match="safe weights-only"):
        trace_module.load_mechanism_trace(tensor_path)


def test_load_old_trace_without_adaptive_fields_uses_defaults(tmp_path):
    tensor_path = tmp_path / "old_trace.pt"
    torch.save(_legacy_tensor_payload(), tensor_path)

    restored = trace_module.load_mechanism_trace(tensor_path)

    assert restored.selection_info == {}
    assert restored.adaptive_rollout_info == {}
    assert restored.chunk_memory_info == {}
    assert restored.search_schedule_info == {}
    assert restored.execution_info == {}
    assert restored.stages[0].parent_probabilities is None
    assert restored.stages[0].parent_selection_kinds is None
