import sys
import json
from csv import DictReader
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.eds_mechanism_trace import (
    EDSMechanismTrace,
    EDSParticleStage,
    build_run_id,
    save_mechanism_trace,
)


def test_build_run_id_encodes_task_reward_and_eds_params():
    run_id = build_run_id(
        suite="libero_object",
        task_id=1,
        seed=0,
        reward_mode="normal",
        population_size=16,
        cem_iters=10,
    )

    assert run_id == "libero_object_task1_seed000_normal_p16_c10"


def test_save_mechanism_trace_writes_metadata_csv_and_tensors(tmp_path):
    stage = EDSParticleStage(
        stage="initial",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            ]
        ),
        rewards=torch.tensor([0.1, 0.2]),
        costs=torch.tensor([-0.1, -0.2]),
        parent_indices=torch.tensor([0, 1]),
    )
    trace = EDSMechanismTrace(
        suite="libero_object",
        task_id=1,
        episode=0,
        global_step=0,
        reward_mode="normal",
        population_size=2,
        cem_iters=1,
        use_cem=False,
        keypoints=torch.tensor([[1.0, 0.0, 0.0]]),
        stages=[stage],
        selected_idx=1,
    )

    paths = save_mechanism_trace(tmp_path, trace, save_tensors=True)

    assert (tmp_path / "first_chunk_metadata.json").exists()
    assert (tmp_path / "single_step_inner_loop" / "single_step_particles.csv").exists()
    assert (tmp_path / "tensors" / "mechanism_trace.pt").exists()
    assert str(tmp_path / "first_chunk_metadata.json") in paths


def test_save_mechanism_trace_records_initial_sampler_metadata(tmp_path):
    stage = EDSParticleStage(
        stage="initial_final",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.zeros(2, 2, 3),
        rewards=torch.tensor([0.1, 0.2]),
        costs=torch.tensor([-0.1, -0.2]),
    )
    trace = EDSMechanismTrace(
        suite="libero_object",
        task_id=1,
        episode=0,
        global_step=0,
        reward_mode="normal",
        population_size=2,
        cem_iters=1,
        use_cem=False,
        keypoints=None,
        stages=[stage],
        selected_idx=1,
        initial_sampler_info={
            "initial_sampling_mode": "rbf_diverse_denoise",
            "initial_diversity_steps": 3,
        },
    )

    save_mechanism_trace(tmp_path, trace, save_tensors=True)

    metadata = json.loads((tmp_path / "first_chunk_metadata.json").read_text())
    assert metadata["initial_sampler_info"]["initial_sampling_mode"] == "rbf_diverse_denoise"
    payload = torch.load(tmp_path / "tensors" / "mechanism_trace.pt")
    assert payload["metadata"]["initial_sampler_info"]["initial_diversity_steps"] == 3


def test_parent_rank_records_pre_resample_parent_order(tmp_path):
    stage = EDSParticleStage(
        stage="resampled",
        iter_idx=0,
        actions=torch.zeros(2, 64, 128),
        trajectories=torch.tensor(
            [
                [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            ]
        ),
        rewards=torch.tensor([0.1, 0.9]),
        costs=torch.tensor([-0.1, -0.9]),
        parent_indices=torch.tensor([2, 0]),
        parent_ranks=torch.tensor([1, 3]),
    )
    trace = EDSMechanismTrace(
        suite="libero_object",
        task_id=1,
        episode=0,
        global_step=0,
        reward_mode="normal",
        population_size=2,
        cem_iters=1,
        use_cem=False,
        keypoints=torch.tensor([[1.0, 0.0, 0.0]]),
        stages=[stage],
        selected_idx=1,
    )

    save_mechanism_trace(tmp_path, trace, save_tensors=False)

    with (tmp_path / "single_step_inner_loop" / "single_step_particles.csv").open(
        newline="",
        encoding="utf-8",
    ) as f:
        rows = list(DictReader(f))
    assert rows[0]["parent_id"] == "2"
    assert rows[0]["parent_rank"] == "1"
    assert rows[0]["reward_rank"] == "2"
    assert rows[1]["parent_id"] == "0"
    assert rows[1]["parent_rank"] == "3"
