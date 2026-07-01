# RDT+EDS Qualitative Mechanism Pretest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an eval-only first-chunk qualitative pretest for real `libero_object` task 1 that saves 3D EDS action-population, keypoint, reward, resampling, renoise, rollout, and full-process artifacts.

**Architecture:** Keep default EDS behavior unchanged and guard all extra capture behind `main.eds_mechanism_pretest.enabled`. Add a small trace schema for mechanism snapshots, capture first-chunk EDS internals inside `RDTSteer._eds_guided_denoise_loop()`, write scalar/tensor artifacts from `main.py`, and generate 3D plots through a focused visualization helper. A script runner provides the single real-task command and optional control runs.

**Tech Stack:** Python, PyTorch, NumPy, pandas/csv, matplotlib 3D plotting, pytest, Hydra/OmegaConf, existing RDTSteer EDS loop, LIBERO adapter.

---

## Source Spec

Approved design:

```text
docs/01_specs/2026-06-12-rdt-eds-qualitative-pretest-design.md
```

Related mechanism-validation plan:

```text
docs/01_specs/rdt_eds_mechanism_validation_plan.md
```

## File Structure

Create:

```text
core/eds_mechanism_trace.py
utils/eds_mechanism_pretest_vis.py
scripts/rdt_eds_mechanism_pretest_runner.py
tests/test_eds_mechanism_trace.py
tests/test_eds_mechanism_pretest_vis.py
tests/test_eds_mechanism_pretest_runner.py
```

Modify:

```text
configs/config.yaml
main.py
core/rdt_policy_steer.py
tests/test_rdt_steer.py
```

Do not modify:

```text
third_party/
docs/03_evidence/eds_steering/ood_eval/
```

Runtime output root:

```text
outputs/rdt_eds_mechanism_pretest/
```

## Implementation Notes

- Capture only generated EDS chunks. Cached action steps must not create repeated artifacts.
- Default behavior must remain unchanged when `main.eds_mechanism_pretest.enabled=false`.
- First pass should run only `reward_mode=normal`, `population_size=16`, `cem_iters=10`, `use_cem=false`, task id `1`, first chunk only.
- RENOISED trajectories are diagnostic projections of noisy action state. The generated figure title or summary must clearly state they are not directly executable.
- Save JSON/CSV scalar summaries for every plotted figure so qualitative interpretation can be checked numerically.
- Keep full tensors opt-in through `save_tensors=true`; scalar CSV/JSON and PNGs are the primary artifacts.

## Task 1: Add Eval-Only Config

**Files:**
- Modify: `configs/config.yaml`
- Test: no dedicated test in this task; config is validated through runner command tests in Task 7.

- [ ] **Step 1: Add `main.eds_mechanism_pretest` config**

In `configs/config.yaml`, add this block under `main.eds_eval`:

```yaml
  eds_mechanism_pretest:
    enabled: false
    first_chunk_only: true
    save_single_step: true
    save_full_process: true
    save_tensors: true
    plot_3d: true
    output_dir: outputs/rdt_eds_mechanism_pretest
    run_id: null
    max_chunks: 1
    max_full_process_iters: 10
```

- [ ] **Step 2: Verify config parses**

Run:

```bash
python - <<'PY'
from omegaconf import OmegaConf
cfg = OmegaConf.load(".worktrees/feat/rdt_ed_steering_integration/configs/config.yaml")
assert cfg.main.eds_mechanism_pretest.enabled is False
assert cfg.main.eds_mechanism_pretest.first_chunk_only is True
assert cfg.main.eds_mechanism_pretest.output_dir == "outputs/rdt_eds_mechanism_pretest"
print("config ok")
PY
```

Expected:

```text
config ok
```

- [ ] **Step 3: Commit Task 1**

```bash
git add configs/config.yaml
git commit -m "config: add EDS mechanism pretest options"
```

## Task 2: Add Trace Schema And Artifact Writer

**Files:**
- Create: `core/eds_mechanism_trace.py`
- Test: `tests/test_eds_mechanism_trace.py`

- [ ] **Step 1: Write failing tests for trace serialization**

Create `tests/test_eds_mechanism_trace.py`:

```python
from pathlib import Path

import torch

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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_eds_mechanism_trace.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'core.eds_mechanism_trace'
```

- [ ] **Step 3: Implement trace schema**

Create `core/eds_mechanism_trace.py`:

```python
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch


@dataclass
class EDSParticleStage:
    stage: str
    iter_idx: int
    actions: torch.Tensor
    trajectories: torch.Tensor
    rewards: torch.Tensor
    costs: torch.Tensor
    parent_indices: torch.Tensor | None = None
    reward_before_rollout: torch.Tensor | None = None
    reward_after_rollout: torch.Tensor | None = None
    renoise_delta_norm: torch.Tensor | None = None
    rollout_delta_norm: torch.Tensor | None = None


@dataclass
class EDSMechanismTrace:
    suite: str | None
    task_id: int | None
    episode: int | None
    global_step: int
    reward_mode: str
    population_size: int
    cem_iters: int
    use_cem: bool
    keypoints: torch.Tensor | None
    stages: list[EDSParticleStage] = field(default_factory=list)
    selected_idx: int | None = None


def build_run_id(
    *,
    suite: str,
    task_id: int,
    seed: int,
    reward_mode: str,
    population_size: int,
    cem_iters: int,
) -> str:
    return (
        f"{suite}_task{int(task_id)}_seed{int(seed):03d}_"
        f"{reward_mode}_p{int(population_size)}_c{int(cem_iters)}"
    )


def _to_cpu(tensor: torch.Tensor | None) -> torch.Tensor | None:
    if tensor is None:
        return None
    return tensor.detach().cpu()


def _distance_rows(stage: EDSParticleStage, keypoints: torch.Tensor | None) -> list[dict[str, Any]]:
    actions = _to_cpu(stage.actions)
    trajectories = _to_cpu(stage.trajectories)
    rewards = _to_cpu(stage.rewards).reshape(-1)
    costs = _to_cpu(stage.costs).reshape(-1)
    parent_indices = _to_cpu(stage.parent_indices)
    before = _to_cpu(stage.reward_before_rollout)
    after = _to_cpu(stage.reward_after_rollout)
    renoise_delta = _to_cpu(stage.renoise_delta_norm)
    rollout_delta = _to_cpu(stage.rollout_delta_norm)
    keypoints_cpu = _to_cpu(keypoints)
    target = keypoints_cpu.reshape(-1, keypoints_cpu.shape[-1])[0, :3] if keypoints_cpu is not None and keypoints_cpu.numel() else None
    ranks = torch.argsort(torch.argsort(-rewards)).to(dtype=torch.long)

    rows: list[dict[str, Any]] = []
    for idx in range(actions.shape[0]):
        traj = trajectories[idx]
        final_distance = ""
        min_distance = ""
        if target is not None:
            distances = torch.linalg.norm(traj[:, :3] - target.to(dtype=traj.dtype), dim=-1)
            final_distance = float(distances[-1].item())
            min_distance = float(distances.min().item())
        trajectory_length = float(torch.linalg.norm(traj[1:, :3] - traj[:-1, :3], dim=-1).sum().item()) if traj.shape[0] > 1 else 0.0
        parent_id = int(parent_indices[idx].item()) if parent_indices is not None else idx
        rows.append(
            {
                "stage": stage.stage,
                "iter_idx": int(stage.iter_idx),
                "particle_id": idx,
                "parent_id": parent_id,
                "parent_rank": "",
                "resampled_count": "",
                "reward": float(rewards[idx].item()),
                "cost": float(costs[idx].item()),
                "reward_rank": int(ranks[idx].item()),
                "distance_to_keypoint_final": final_distance,
                "distance_to_keypoint_min": min_distance,
                "trajectory_length": trajectory_length,
                "renoise_delta_norm": float(renoise_delta[idx].item()) if renoise_delta is not None else "",
                "rollout_delta_norm": float(rollout_delta[idx].item()) if rollout_delta is not None else "",
                "reward_before_rollout": float(before[idx].item()) if before is not None else "",
                "reward_after_rollout": float(after[idx].item()) if after is not None else "",
            }
        )
    return rows


def save_mechanism_trace(output_dir: str | Path, trace: EDSMechanismTrace, *, save_tensors: bool) -> list[str]:
    root = Path(output_dir)
    single_step_dir = root / "single_step_inner_loop"
    tensors_dir = root / "tensors"
    single_step_dir.mkdir(parents=True, exist_ok=True)
    if save_tensors:
        tensors_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "suite": trace.suite,
        "task_id": trace.task_id,
        "episode": trace.episode,
        "global_step": trace.global_step,
        "reward_mode": trace.reward_mode,
        "population_size": trace.population_size,
        "cem_iters": trace.cem_iters,
        "use_cem": trace.use_cem,
        "selected_idx": trace.selected_idx,
        "stage_count": len(trace.stages),
    }
    saved: list[str] = []
    metadata_path = root / "first_chunk_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    saved.append(str(metadata_path))

    csv_path = single_step_dir / "single_step_particles.csv"
    rows = []
    for stage in trace.stages:
        rows.extend(_distance_rows(stage, trace.keypoints))
    fieldnames = [
        "stage",
        "iter_idx",
        "particle_id",
        "parent_id",
        "parent_rank",
        "resampled_count",
        "reward",
        "cost",
        "reward_rank",
        "distance_to_keypoint_final",
        "distance_to_keypoint_min",
        "trajectory_length",
        "renoise_delta_norm",
        "rollout_delta_norm",
        "reward_before_rollout",
        "reward_after_rollout",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    saved.append(str(csv_path))

    if save_tensors:
        tensor_path = tensors_dir / "mechanism_trace.pt"
        torch.save(trace, tensor_path)
        saved.append(str(tensor_path))
    return saved
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_eds_mechanism_trace.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit Task 2**

```bash
git add core/eds_mechanism_trace.py tests/test_eds_mechanism_trace.py
git commit -m "feat: add EDS mechanism trace schema"
```

## Task 3: Capture EDS First-Chunk Mechanism Trace

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `main.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Write failing tests for trace capture**

Append to `tests/test_rdt_steer.py`:

```python
def test_eds_mechanism_pretest_trace_records_single_step_stages(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 8},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: -torch.linalg.norm(traj[:, -1, :3] - keypoints[0, :3], dim=-1).sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 2,
            "temperature": 0.1,
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": 2,
            },
        },
        global_step=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    assert trace is not None
    assert trace.global_step == 0
    assert trace.population_size == 3
    assert {stage.stage for stage in trace.stages} >= {
        "initial",
        "scored",
        "resampled",
        "renoised",
        "after_rollout",
    }


def test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 8},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "mechanism_pretest": {"enabled": True, "first_chunk_only": True},
        },
        global_step=8,
    )

    assert stub_steer.get_last_eds_mechanism_trace() is None
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_mechanism_pretest_trace_records_single_step_stages tests/test_rdt_steer.py::test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks -q
```

Expected:

```text
FAIL with AttributeError for get_last_eds_mechanism_trace or missing mechanism_pretest config
```

- [ ] **Step 3: Extend EDS config and public getter**

In `core/rdt_policy_steer.py`, import trace classes near existing EDS metrics imports:

```python
from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage
```

Add a field to `_EDSConfig`:

```python
mechanism_pretest: Optional[dict] = None
```

In `RDTSteer.__init__`, add:

```python
self._last_eds_mechanism_trace: Optional[EDSMechanismTrace] = None
```

Add getter next to `get_last_eds_artifacts()`:

```python
def get_last_eds_mechanism_trace(self) -> Optional[EDSMechanismTrace]:
    return self._last_eds_mechanism_trace
```

Reset the field where `_last_eds_metrics` and `_last_eds_artifacts` are reset.

- [ ] **Step 4: Preserve mechanism pretest config in resolver**

In `_resolve_eds_config_with_reference_defaults()`, add:

```python
mechanism_pretest=cfg.get("mechanism_pretest"),
```

to the `_EDSConfig(...)` construction.

- [ ] **Step 5: Add trajectory and trace helper methods**

In `core/rdt_policy_steer.py`, add these helper methods near existing EDS helper methods:

```python
def _eds_pretest_enabled(self, cfg: _EDSConfig, global_step: int) -> bool:
    pretest = cfg.mechanism_pretest
    if not isinstance(pretest, dict) or not bool(pretest.get("enabled", False)):
        return False
    if bool(pretest.get("first_chunk_only", True)) and int(global_step) != 0:
        return False
    return True


def _eds_population_to_reward_trajectories(self, population: Tensor) -> Tensor:
    return self._trajectory_reward_slice(
        self._rdt_sample_to_trajectory_3d(population),
        "eds",
    )


def _eds_make_trace_stage(
    self,
    *,
    stage: str,
    iter_idx: int,
    population: Tensor,
    costs: Tensor,
    info: dict,
    parent_indices: Optional[Tensor] = None,
    reward_before_rollout: Optional[Tensor] = None,
    reward_after_rollout: Optional[Tensor] = None,
    renoise_delta_norm: Optional[Tensor] = None,
    rollout_delta_norm: Optional[Tensor] = None,
) -> EDSParticleStage:
    rewards = self._eds_rewards_from_info(costs, info)
    return EDSParticleStage(
        stage=stage,
        iter_idx=int(iter_idx),
        actions=population.detach().cpu(),
        trajectories=self._eds_population_to_reward_trajectories(population).detach().cpu(),
        rewards=rewards.detach().cpu(),
        costs=costs.detach().cpu(),
        parent_indices=parent_indices.detach().cpu() if parent_indices is not None else None,
        reward_before_rollout=reward_before_rollout.detach().cpu() if reward_before_rollout is not None else None,
        reward_after_rollout=reward_after_rollout.detach().cpu() if reward_after_rollout is not None else None,
        renoise_delta_norm=renoise_delta_norm.detach().cpu() if renoise_delta_norm is not None else None,
        rollout_delta_norm=rollout_delta_norm.detach().cpu() if rollout_delta_norm is not None else None,
    )
```

- [ ] **Step 6: Capture stages inside `_eds_guided_denoise_loop()`**

Inside `_eds_guided_denoise_loop()`, after initial scoring, initialize:

```python
trace_enabled = self._eds_pretest_enabled(cfg, global_step)
trace_stages: list[EDSParticleStage] = []
if trace_enabled:
    trace_stages.append(
        self._eds_make_trace_stage(
            stage="initial",
            iter_idx=0,
            population=population,
            costs=population_scores,
            info=population_info,
        )
    )
    trace_stages.append(
        self._eds_make_trace_stage(
            stage="scored",
            iter_idx=0,
            population=population,
            costs=population_scores,
            info=population_info,
        )
    )
```

Inside each CEM/MPPI resampling branch, keep `parent_indices` as the original selected parent tensor. Immediately after `population = population[...]`, add:

```python
if trace_enabled and i == 0:
    trace_stages.append(
        self._eds_make_trace_stage(
            stage="resampled",
            iter_idx=i,
            population=population,
            costs=population_scores.index_select(0, parent_indices.to(device=population_scores.device)),
            info={"rewards": population_rewards.index_select(0, parent_indices.to(device=population_rewards.device))},
            parent_indices=parent_indices,
        )
    )
```

Before renoise, keep:

```python
population_before_renoise = population
reward_before_rollout = population_rewards.index_select(0, parent_indices.to(device=population_rewards.device))
```

After renoise:

```python
renoised_population = population
renoise_delta_norm = (renoised_population - population_before_renoise).reshape(population.shape[0], -1).norm(dim=1)
if trace_enabled and i == 0:
    renoise_costs, renoise_info = self._eds_score_population_as_cost(
        renoised_population,
        keypoints=keypoints,
        guidance_fns=guidance_fns,
        reward_mode=cfg.reward_mode,
        shuffle_seed=cfg.shuffle_seed,
    )
    trace_stages.append(
        self._eds_make_trace_stage(
            stage="renoised",
            iter_idx=i,
            population=renoised_population,
            costs=renoise_costs,
            info=renoise_info,
            parent_indices=parent_indices,
            reward_before_rollout=reward_before_rollout,
            renoise_delta_norm=renoise_delta_norm,
        )
    )
```

Before rollout, set:

```python
population_before_rollout = population
```

After rollout and scoring:

```python
rollout_delta_norm = (population - population_before_rollout).reshape(population.shape[0], -1).norm(dim=1)
if trace_enabled:
    if i == 0:
        trace_stages.append(
            self._eds_make_trace_stage(
                stage="after_rollout",
                iter_idx=i,
                population=population,
                costs=population_scores,
                info=population_info,
                parent_indices=parent_indices,
                reward_before_rollout=reward_before_rollout,
                reward_after_rollout=population_rewards,
                renoise_delta_norm=renoise_delta_norm,
                rollout_delta_norm=rollout_delta_norm,
            )
        )
    if bool(cfg.mechanism_pretest.get("save_full_process", True)):
        trace_stages.append(
            self._eds_make_trace_stage(
                stage="full_process_after_rollout",
                iter_idx=i,
                population=population,
                costs=population_scores,
                info=population_info,
            )
        )
```

After final selection, set:

```python
if trace_enabled:
    self._last_eds_mechanism_trace = EDSMechanismTrace(
        suite=None,
        task_id=None,
        episode=None,
        global_step=int(global_step),
        reward_mode=cfg.reward_mode,
        population_size=cfg.population_size,
        cem_iters=cfg.cem_iters,
        use_cem=cfg.use_cem,
        keypoints=keypoints.detach().cpu() if keypoints is not None else None,
        stages=trace_stages,
        selected_idx=best_idx,
    )
else:
    self._last_eds_mechanism_trace = None
```

- [ ] **Step 7: Pass mechanism config from main into EDS config**

In `main.py`, after `eds_eval_config` is created, add:

```python
eds_pretest_config = _config_section_to_dict(
    self.config.get("eds_mechanism_pretest"),
    "main.eds_mechanism_pretest",
)
if eds_pretest_config:
    eds_config["mechanism_pretest"] = eds_pretest_config
```

- [ ] **Step 8: Run tests and verify they pass**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_mechanism_pretest_trace_records_single_step_stages tests/test_rdt_steer.py::test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks -q
```

Expected:

```text
2 passed
```

- [ ] **Step 9: Commit Task 3**

```bash
git add core/rdt_policy_steer.py main.py tests/test_rdt_steer.py
git commit -m "feat: capture first-chunk EDS mechanism trace"
```

## Task 4: Add 3D Pretest Visualization Helper

**Files:**
- Create: `utils/eds_mechanism_pretest_vis.py`
- Test: `tests/test_eds_mechanism_pretest_vis.py`

- [ ] **Step 1: Write failing visualization tests**

Create `tests/test_eds_mechanism_pretest_vis.py`:

```python
import torch

from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage
from utils.eds_mechanism_pretest_vis import save_eds_mechanism_pretest_artifacts


def _trace():
    stages = [
        EDSParticleStage(
            stage="initial",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.1, 0.2]),
            costs=torch.tensor([-0.1, -0.2]),
        ),
        EDSParticleStage(
            stage="after_rollout",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.tensor(
                [
                    [[0.0, 0.0, 0.0], [1.2, 0.0, 0.0]],
                    [[0.0, 0.0, 0.0], [0.0, 1.2, 0.0]],
                ],
                dtype=torch.float32,
            ),
            rewards=torch.tensor([0.3, 0.4]),
            costs=torch.tensor([-0.3, -0.4]),
        ),
    ]
    return EDSMechanismTrace(
        suite="libero_object",
        task_id=1,
        episode=0,
        global_step=0,
        reward_mode="normal",
        population_size=2,
        cem_iters=1,
        use_cem=False,
        keypoints=torch.tensor([[1.0, 0.0, 0.0]]),
        stages=stages,
        selected_idx=1,
    )


def test_save_eds_mechanism_pretest_artifacts_writes_pngs_and_summary(tmp_path):
    saved = save_eds_mechanism_pretest_artifacts(tmp_path, _trace())

    assert (tmp_path / "single_step_inner_loop" / "00_initial_population_3d.png").exists()
    assert (tmp_path / "single_step_inner_loop" / "04_after_rollout_3d.png").exists()
    assert (tmp_path / "full_eds_process" / "reward_curve.png").exists()
    assert (tmp_path / "full_eds_process" / "full_process_summary.md").exists()
    assert any(path.endswith("reward_curve.png") for path in saved)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_vis.py -q
```

Expected:

```text
FAIL with ModuleNotFoundError: No module named 'utils.eds_mechanism_pretest_vis'
```

- [ ] **Step 3: Implement visualization helper**

Create `utils/eds_mechanism_pretest_vis.py`:

```python
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from core.eds_mechanism_trace import EDSMechanismTrace, EDSParticleStage


def _to_numpy(tensor: torch.Tensor | None) -> np.ndarray | None:
    if tensor is None:
        return None
    return tensor.detach().cpu().float().numpy()


def _axis_limits(stages: list[EDSParticleStage], keypoints: torch.Tensor | None) -> tuple[np.ndarray, np.ndarray]:
    points = []
    for stage in stages:
        trajs = _to_numpy(stage.trajectories)
        if trajs is not None and trajs.size:
            points.append(trajs.reshape(-1, 3))
    keypoints_np = _to_numpy(keypoints)
    if keypoints_np is not None and keypoints_np.size:
        points.append(keypoints_np.reshape(-1, keypoints_np.shape[-1])[:, :3])
    if not points:
        return np.array([-1.0, -1.0, -1.0]), np.array([1.0, 1.0, 1.0])
    all_points = np.concatenate(points, axis=0)
    mins = np.nanmin(all_points, axis=0)
    maxs = np.nanmax(all_points, axis=0)
    span = np.maximum(maxs - mins, 1e-3)
    pad = span.max() * 0.15
    return mins - pad, maxs + pad


def _plot_stage(path: Path, trace: EDSMechanismTrace, stage: EDSParticleStage, *, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trajectories = _to_numpy(stage.trajectories)
    rewards = _to_numpy(stage.rewards).reshape(-1)
    keypoints = _to_numpy(trace.keypoints)
    mins, maxs = _axis_limits(trace.stages, trace.keypoints)

    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(111, projection="3d")
    cmap = plt.get_cmap("viridis")
    reward_min = float(np.nanmin(rewards)) if rewards.size else 0.0
    reward_max = float(np.nanmax(rewards)) if rewards.size else 1.0
    denom = max(reward_max - reward_min, 1e-8)
    for idx, traj in enumerate(trajectories):
        color = cmap((float(rewards[idx]) - reward_min) / denom)
        width = 3.0 if trace.selected_idx is not None and idx == int(trace.selected_idx) else 1.2
        ax.plot(traj[:, 0], traj[:, 1], traj[:, 2], color=color, alpha=0.8, linewidth=width)
        ax.scatter(traj[-1, 0], traj[-1, 1], traj[-1, 2], color=color, s=16)
    if trajectories.size:
        start = trajectories[0, 0]
        ax.scatter(start[0], start[1], start[2], color="black", s=55, label="start EEF")
    if keypoints is not None and keypoints.size:
        kp = keypoints.reshape(-1, keypoints.shape[-1])[:, :3]
        ax.scatter(kp[:, 0], kp[:, 1], kp[:, 2], color="red", marker="*", s=130, label="keypoint")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=reward_min, vmax=reward_max))
    fig.colorbar(sm, ax=ax, shrink=0.7, label="reward")
    ax.set_xlim(float(mins[0]), float(maxs[0]))
    ax.set_ylim(float(mins[1]), float(maxs[1]))
    ax.set_zlim(float(mins[2]), float(maxs[2]))
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_title(title)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_curves(path: Path, trace: EDSMechanismTrace, metric: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stages = [s for s in trace.stages if s.stage == "full_process_after_rollout" or s.stage == "after_rollout"]
    if not stages:
        stages = trace.stages
    xs = [s.iter_idx for s in stages]
    best = [float(s.rewards.max().item()) for s in stages]
    mean = [float(s.rewards.float().mean().item()) for s in stages]
    std = [float(s.rewards.float().std(unbiased=False).item()) for s in stages]
    fig, ax = plt.subplots(figsize=(7, 4))
    if metric == "reward":
        ax.plot(xs, best, label="best_reward")
        ax.plot(xs, mean, label="mean_reward")
        ax.fill_between(xs, np.array(mean) - np.array(std), np.array(mean) + np.array(std), alpha=0.2, label="reward_std")
        ax.set_ylabel("reward")
    else:
        diversity = []
        for stage in stages:
            flat = stage.trajectories.reshape(stage.trajectories.shape[0], -1).float()
            diversity.append(float(torch.pdist(flat).mean().item()) if flat.shape[0] > 1 else 0.0)
        ax.plot(xs, diversity, label="eef_diversity")
        ax.set_ylabel("diversity")
    ax.set_xlabel("iter")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def save_eds_mechanism_pretest_artifacts(output_dir: str | Path, trace: EDSMechanismTrace) -> list[str]:
    root = Path(output_dir)
    single = root / "single_step_inner_loop"
    full = root / "full_eds_process"
    saved: list[str] = []
    stage_to_file = {
        "initial": "00_initial_population_3d.png",
        "scored": "01_scored_population_3d.png",
        "resampled": "02_after_resample_3d.png",
        "renoised": "03_after_renoise_3d.png",
        "after_rollout": "04_after_rollout_3d.png",
    }
    for stage in trace.stages:
        if stage.stage in stage_to_file and stage.iter_idx == 0:
            path = single / stage_to_file[stage.stage]
            _plot_stage(path, trace, stage, title=f"{stage.stage} iter={stage.iter_idx} reward_mode={trace.reward_mode}")
            saved.append(str(path))
        if stage.stage in {"full_process_after_rollout", "after_rollout"}:
            path = full / f"iter_{stage.iter_idx:03d}_population_3d.png"
            _plot_stage(path, trace, stage, title=f"full EDS iter={stage.iter_idx} reward_mode={trace.reward_mode}")
            saved.append(str(path))

    reward_curve = full / "reward_curve.png"
    _plot_curves(reward_curve, trace, "reward")
    saved.append(str(reward_curve))
    diversity_curve = full / "diversity_curve.png"
    _plot_curves(diversity_curve, trace, "diversity")
    saved.append(str(diversity_curve))
    summary = full / "full_process_summary.md"
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(
        "\n".join(
            [
                "# EDS Mechanism Pretest Summary",
                "",
                f"- suite: `{trace.suite}`",
                f"- task_id: `{trace.task_id}`",
                f"- reward_mode: `{trace.reward_mode}`",
                f"- population_size: `{trace.population_size}`",
                f"- cem_iters: `{trace.cem_iters}`",
                f"- selected_idx: `{trace.selected_idx}`",
                "",
                "Renoised trajectory plots are diagnostic projections of noisy action state, not directly executable actions.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    saved.append(str(summary))
    return saved
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_vis.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit Task 4**

```bash
git add utils/eds_mechanism_pretest_vis.py tests/test_eds_mechanism_pretest_vis.py
git commit -m "feat: add EDS mechanism pretest 3D plots"
```

## Task 5: Write Pretest Artifacts From Main

**Files:**
- Modify: `main.py`
- Test: `tests/test_main_rdt_startup.py` or a new focused test if existing main tests are too heavy.

- [ ] **Step 1: Add imports in `main.py`**

Add:

```python
from core.eds_mechanism_trace import build_run_id, save_mechanism_trace
from utils.eds_mechanism_pretest_vis import save_eds_mechanism_pretest_artifacts
```

- [ ] **Step 2: Save trace after generated EDS chunk**

Inside the existing `generate_new_chunk and use_guidance and guidance_type == "eds"` metrics block, after normal EDS metrics writing, add:

```python
if (
    generate_new_chunk
    and use_guidance
    and guidance_type == "eds"
    and eds_pretest_config.get("enabled", False)
    and hasattr(self.policy, "get_last_eds_mechanism_trace")
):
    trace = self.policy.get_last_eds_mechanism_trace()
    if trace is not None:
        trace.suite = getattr(self.adapter, "suite_name", None)
        trace.task_id = getattr(self.adapter, "current_task_idx", None)
        trace.episode = int(episode)
        seed = int(eds_pretest_config.get("seed", 0))
        run_id = eds_pretest_config.get("run_id") or build_run_id(
            suite=str(trace.suite or "unknown_suite"),
            task_id=int(trace.task_id if trace.task_id is not None else -1),
            seed=seed,
            reward_mode=str(trace.reward_mode),
            population_size=int(trace.population_size),
            cem_iters=int(trace.cem_iters),
        )
        pretest_root = Path(eds_pretest_config.get("output_dir", "outputs/rdt_eds_mechanism_pretest")) / run_id
        saved_trace_paths = save_mechanism_trace(
            pretest_root,
            trace,
            save_tensors=bool(eds_pretest_config.get("save_tensors", True)),
        )
        saved_plot_paths = []
        if bool(eds_pretest_config.get("plot_3d", True)):
            saved_plot_paths = save_eds_mechanism_pretest_artifacts(pretest_root, trace)
        log.info(
            "[EDS_PRETEST] saved %d trace artifacts and %d plot artifacts to %s",
            len(saved_trace_paths),
            len(saved_plot_paths),
            pretest_root,
        )
```

- [ ] **Step 3: Run existing import and startup tests**

Run:

```bash
pytest tests/test_main_rdt_startup.py -q
```

Expected:

```text
all tests pass
```

If this test file is not present or does not cover import, run:

```bash
python -m py_compile main.py core/rdt_policy_steer.py core/eds_mechanism_trace.py utils/eds_mechanism_pretest_vis.py
```

Expected:

```text
exit code 0
```

- [ ] **Step 4: Commit Task 5**

```bash
git add main.py
git commit -m "feat: write EDS mechanism pretest artifacts"
```

## Task 6: Add Runner For One-Chunk Task1 Pretest

**Files:**
- Create: `scripts/rdt_eds_mechanism_pretest_runner.py`
- Test: `tests/test_eds_mechanism_pretest_runner.py`

- [ ] **Step 1: Write failing runner tests**

Create `tests/test_eds_mechanism_pretest_runner.py`:

```python
import importlib.util
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_mechanism_pretest_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_mechanism_pretest_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build_pretest_command_targets_libero_object_task1_first_chunk():
    runner = _load_runner()
    cmd = runner.build_pretest_command(reward_mode="normal", output_root=Path("outputs/pretest"))

    assert "policy.type=rdt" in cmd
    assert "backend.libero.suite_name=libero_object" in cmd
    assert "backend.libero.task_ids_filter=[1]" in cmd
    assert "main.episode_num=1" in cmd
    assert "main.guidance_type=eds" in cmd
    assert "main.eds_config.population_size=16" in cmd
    assert "main.eds_config.cem_iters=10" in cmd
    assert "main.eds_eval.reward_mode=normal" in cmd
    assert "main.eds_mechanism_pretest.enabled=true" in cmd
    assert "main.eds_mechanism_pretest.first_chunk_only=true" in cmd
    assert "main.eds_mechanism_pretest.output_dir=outputs/pretest" in cmd


def test_build_control_commands_include_zero_and_inverted_only():
    runner = _load_runner()
    commands = runner.build_control_commands(output_root=Path("outputs/pretest"))
    joined = [" ".join(cmd) for cmd in commands]

    assert any("main.eds_eval.reward_mode=zero" in item for item in joined)
    assert any("main.eds_eval.reward_mode=inverted" in item for item in joined)
    assert not any("shuffled_keypoints" in item for item in joined)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_runner.py -q
```

Expected:

```text
FAIL with FileNotFoundError or ModuleNotFoundError for runner
```

- [ ] **Step 3: Implement runner**

Create `scripts/rdt_eds_mechanism_pretest_runner.py`:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

WORKTREE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_mechanism_pretest"


def build_pretest_command(*, reward_mode: str, output_root: Path) -> list[str]:
    return [
        "python",
        "main.py",
        "policy.type=rdt",
        "backend=libero",
        "backend.libero.suite_name=libero_object",
        "backend.libero.task_ids_filter=[1]",
        "backend.libero.max_episode_steps=240",
        "main.episode_num=1",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        "main.render=false",
        "main.visualize_trajectory=false",
        "main.debug_draw_trajectory=false",
        "main.use_guidance=true",
        "main.guidance_type=eds",
        "main.eds_config.population_size=16",
        "main.eds_config.cem_iters=10",
        "main.eds_config.use_cem=false",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=false",
        f"main.eds_eval.reward_mode={reward_mode}",
        "main.eds_mechanism_pretest.enabled=true",
        "main.eds_mechanism_pretest.first_chunk_only=true",
        "main.eds_mechanism_pretest.save_single_step=true",
        "main.eds_mechanism_pretest.save_full_process=true",
        "main.eds_mechanism_pretest.save_tensors=true",
        "main.eds_mechanism_pretest.plot_3d=true",
        f"main.eds_mechanism_pretest.output_dir={output_root}",
        f"hydra.run.dir={output_root / ('hydra_' + reward_mode)}",
    ]


def build_control_commands(*, output_root: Path) -> list[list[str]]:
    return [
        build_pretest_command(reward_mode="zero", output_root=output_root),
        build_pretest_command(reward_mode="inverted", output_root=output_root),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the RDT+EDS qualitative mechanism pretest.")
    parser.add_argument("--reward-mode", default="normal", choices=["normal", "zero", "inverted"])
    parser.add_argument("--controls", action="store_true", help="Run zero and inverted controls instead of the normal run.")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    commands = build_control_commands(output_root=args.output_root) if args.controls else [
        build_pretest_command(reward_mode=args.reward_mode, output_root=args.output_root)
    ]
    for cmd in commands:
        print(" ".join(str(part) for part in cmd))
        if not args.dry_run:
            subprocess.run(cmd, cwd=WORKTREE_ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run runner tests**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_runner.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Dry-run the normal command**

Run:

```bash
python scripts/rdt_eds_mechanism_pretest_runner.py --dry-run --reward-mode normal
```

Expected output contains:

```text
backend.libero.task_ids_filter=[1]
main.eds_mechanism_pretest.enabled=true
main.eds_eval.reward_mode=normal
```

- [ ] **Step 6: Commit Task 6**

```bash
git add scripts/rdt_eds_mechanism_pretest_runner.py tests/test_eds_mechanism_pretest_runner.py
git commit -m "feat: add EDS mechanism pretest runner"
```

## Task 7: Add Review Summary Generation

**Files:**
- Modify: `utils/eds_mechanism_pretest_vis.py`
- Test: `tests/test_eds_mechanism_pretest_vis.py`

- [ ] **Step 1: Extend visualization test for review checklist**

In `tests/test_eds_mechanism_pretest_vis.py`, add:

```python
def test_summary_contains_review_protocol(tmp_path):
    save_eds_mechanism_pretest_artifacts(tmp_path, _trace())
    summary = (tmp_path / "full_eds_process" / "full_process_summary.md").read_text(encoding="utf-8")

    assert "Qualitative Review Checklist" in summary
    assert "reward geometry" in summary
    assert "resampling pressure" in summary
    assert "rollout preservation" in summary
    assert "pass / mixed / fail" in summary
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_vis.py::test_summary_contains_review_protocol -q
```

Expected:

```text
FAIL because summary lacks review checklist
```

- [ ] **Step 3: Update summary markdown**

In `save_eds_mechanism_pretest_artifacts()`, replace the `summary.write_text(...)` content with:

```python
summary.write_text(
    "\n".join(
        [
            "# EDS Mechanism Pretest Summary",
            "",
            f"- suite: `{trace.suite}`",
            f"- task_id: `{trace.task_id}`",
            f"- reward_mode: `{trace.reward_mode}`",
            f"- population_size: `{trace.population_size}`",
            f"- cem_iters: `{trace.cem_iters}`",
            f"- selected_idx: `{trace.selected_idx}`",
            "",
            "Renoised trajectory plots are diagnostic projections of noisy action state, not directly executable actions.",
            "",
            "## Qualitative Review Checklist",
            "",
            "- population diversity: pass / mixed / fail",
            "- reward geometry: pass / mixed / fail",
            "- resampling pressure: pass / mixed / fail",
            "- renoise scale: pass / mixed / fail",
            "- rollout preservation: pass / mixed / fail",
            "- full-process trend: pass / mixed / fail",
            "- final selected plausibility: pass / mixed / fail",
            "",
            "## Reviewer Notes",
            "",
            "- Overall verdict: pass / mixed / fail",
            "- Notes:",
        ]
    )
    + "\n",
    encoding="utf-8",
)
```

- [ ] **Step 4: Run visualization tests**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_vis.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Commit Task 7**

```bash
git add utils/eds_mechanism_pretest_vis.py tests/test_eds_mechanism_pretest_vis.py
git commit -m "docs: add EDS pretest review checklist"
```

## Task 8: Full Regression And Real Pretest Command

**Files:**
- No new files unless fixing failures from previous tasks.

- [ ] **Step 1: Run focused unit tests**

Run:

```bash
pytest \
  tests/test_eds_mechanism_trace.py \
  tests/test_eds_mechanism_pretest_vis.py \
  tests/test_eds_mechanism_pretest_runner.py \
  tests/test_rdt_steer.py::test_eds_mechanism_pretest_trace_records_single_step_stages \
  tests/test_rdt_steer.py::test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks \
  -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run import/compile checks**

Run:

```bash
python -m py_compile \
  main.py \
  core/rdt_policy_steer.py \
  core/eds_mechanism_trace.py \
  utils/eds_mechanism_pretest_vis.py \
  scripts/rdt_eds_mechanism_pretest_runner.py
```

Expected:

```text
exit code 0
```

- [ ] **Step 3: Run the normal real pretest**

Run from the worktree root with required API keys available:

```bash
python scripts/rdt_eds_mechanism_pretest_runner.py --reward-mode normal
```

Expected artifacts:

```text
outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_normal_p16_c10/
  first_chunk_metadata.json
  single_step_inner_loop/single_step_particles.csv
  single_step_inner_loop/00_initial_population_3d.png
  single_step_inner_loop/01_scored_population_3d.png
  single_step_inner_loop/02_after_resample_3d.png
  single_step_inner_loop/03_after_renoise_3d.png
  single_step_inner_loop/04_after_rollout_3d.png
  full_eds_process/reward_curve.png
  full_eds_process/diversity_curve.png
  full_eds_process/full_process_summary.md
  tensors/mechanism_trace.pt
```

- [ ] **Step 4: Run artifact existence check**

Run:

```bash
python - <<'PY'
from pathlib import Path
root = Path("outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_normal_p16_c10")
required = [
    "first_chunk_metadata.json",
    "single_step_inner_loop/single_step_particles.csv",
    "single_step_inner_loop/00_initial_population_3d.png",
    "single_step_inner_loop/01_scored_population_3d.png",
    "single_step_inner_loop/02_after_resample_3d.png",
    "single_step_inner_loop/03_after_renoise_3d.png",
    "single_step_inner_loop/04_after_rollout_3d.png",
    "full_eds_process/reward_curve.png",
    "full_eds_process/diversity_curve.png",
    "full_eds_process/full_process_summary.md",
    "tensors/mechanism_trace.pt",
]
missing = [item for item in required if not (root / item).exists()]
print("missing=", missing)
raise SystemExit(1 if missing else 0)
PY
```

Expected:

```text
missing= []
```

- [ ] **Step 5: Optional control dry-run**

Run:

```bash
python scripts/rdt_eds_mechanism_pretest_runner.py --dry-run --controls
```

Expected output contains one command with:

```text
main.eds_eval.reward_mode=zero
```

and one command with:

```text
main.eds_eval.reward_mode=inverted
```

- [ ] **Step 6: Commit Task 8**

```bash
git add .
git commit -m "test: verify EDS mechanism pretest pipeline"
```

## Final Verification

Before marking the implementation complete, run:

```bash
pytest \
  tests/test_eds_mechanism_trace.py \
  tests/test_eds_mechanism_pretest_vis.py \
  tests/test_eds_mechanism_pretest_runner.py \
  tests/test_rdt_steer.py::test_eds_mechanism_pretest_trace_records_single_step_stages \
  tests/test_rdt_steer.py::test_eds_mechanism_pretest_first_chunk_only_skips_later_chunks \
  -q

python -m py_compile \
  main.py \
  core/rdt_policy_steer.py \
  core/eds_mechanism_trace.py \
  utils/eds_mechanism_pretest_vis.py \
  scripts/rdt_eds_mechanism_pretest_runner.py

python scripts/rdt_eds_mechanism_pretest_runner.py --dry-run --reward-mode normal
```

For a real artifact-producing validation, run:

```bash
python scripts/rdt_eds_mechanism_pretest_runner.py --reward-mode normal
```

Then verify:

```bash
python - <<'PY'
from pathlib import Path
root = Path("outputs/rdt_eds_mechanism_pretest/libero_object_task1_seed000_normal_p16_c10")
required = [
    "first_chunk_metadata.json",
    "single_step_inner_loop/single_step_particles.csv",
    "single_step_inner_loop/00_initial_population_3d.png",
    "single_step_inner_loop/01_scored_population_3d.png",
    "single_step_inner_loop/02_after_resample_3d.png",
    "single_step_inner_loop/03_after_renoise_3d.png",
    "single_step_inner_loop/04_after_rollout_3d.png",
    "full_eds_process/reward_curve.png",
    "full_eds_process/diversity_curve.png",
    "full_eds_process/full_process_summary.md",
    "tensors/mechanism_trace.pt",
]
missing = [item for item in required if not (root / item).exists()]
print("missing=", missing)
raise SystemExit(1 if missing else 0)
PY
```

## Handoff Notes

- This plan intentionally captures first-chunk mechanism evidence only.
- The pretest does not replace the full mechanism validation plan.
- If the normal reward visualization fails, debug reward/keypoint/coordinate semantics before adding larger ablations or OOD runs.
- If normal looks coherent, rerun the same script with `--controls` to produce zero and inverted qualitative controls.
