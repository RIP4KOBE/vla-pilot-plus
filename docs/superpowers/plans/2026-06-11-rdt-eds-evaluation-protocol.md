# RDT+EDS Evaluation Protocol Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the evaluation harness, instrumentation, qualitative artifacts, and report generation needed to verify RDT+EDS deployment correctness and algorithm effectiveness on `libero_object` and LIBERO-PRO `libero_object_*` perturbations.

**Architecture:** Keep the EDS algorithm inside `core/rdt_policy_steer.py`, but expose structured per-chunk traces through a small metrics module. `main.py` writes JSONL metrics and optional qualitative artifacts during normal evaluation runs. A new RDT+EDS-only runner orchestrates Level 0 through Level 4, generates per-level reports after each level, and produces a final cross-level report.

**Tech Stack:** Python, PyTorch, Hydra/OmegaConf, pytest, CSV/JSONL, OpenCV/imageio for visualization, tmux shell wrapper, LIBERO/LIBERO-PRO.

---

## File Structure

- Create `core/eds_eval_metrics.py`
  - Owns serializable EDS trace dataclasses, JSONL helpers, metric math, and gate evaluators.

- Create `utils/eds_eval_vis.py`
  - Owns qualitative visualization helpers for keypoint overlays, selected EEF trajectories, per-iteration best trajectories, population clouds, and initial-vs-final comparisons.

- Modify `configs/config.yaml`
  - Adds `main.eds_eval` options for structured metrics, qualitative artifact saving, reward ablation mode, and report locations.

- Modify `core/rdt_policy_steer.py`
  - Adds EDS reward ablation modes: `normal`, `zero`, `shuffled_keypoints`, `inverted`.
  - Records Level-0 and Level-1 counters/metrics in `_last_eds_metrics`.
  - Stores lightweight qualitative trace arrays in `_last_eds_artifacts`.
  - Exposes `get_last_eds_metrics()` and `get_last_eds_artifacts()`.

- Modify `main.py`
  - Measures `select_action_latency_s`.
  - Writes `eds_metrics.jsonl` after every generated EDS action chunk.
  - Saves qualitative artifacts when `main.eds_eval.save_qualitative=true`.

- Create `scripts/rdt_eds_eval_runner.py`
  - RDT+EDS-only runner for preflight, Level 0, Level 1, Level 2, Level 3, Level 4, status, and report generation.
  - Does not include VLS, PI05, `libero_spatial`, `libero_goal`, or `libero_10`.

- Create `scripts/run_rdt_eds_eval.sh`
  - Shell wrapper with tmux support so evaluation continues after SSH disconnect.

- Create `tests/test_eds_eval_metrics.py`
  - Unit tests for JSONL serialization, metric summaries, gate logic, and Wilson confidence intervals.

- Create `tests/test_eds_eval_runner.py`
  - Unit tests for manifest construction, command generation, scope restrictions, and report file naming.

- Modify `tests/test_rdt_steer.py`
  - Adds tests for EDS trace counters, ablation modes, selected-best consistency, and finite population scores.

- Modify `tests/test_main_rdt_startup.py`
  - Adds tests that `main.py` writes EDS metrics and invokes qualitative artifact saving only for generated EDS chunks.

- Do not modify `third_party/RoboticsDiffusionTransformer-diffusion-es`.

---

### Task 1: Add Evaluation Config And Metrics Schema

**Files:**
- Modify: `configs/config.yaml`
- Create: `core/eds_eval_metrics.py`
- Test: `tests/test_eds_eval_metrics.py`

- [ ] **Step 1: Add `main.eds_eval` config**

In `configs/config.yaml`, add this block under `main.eds_config`:

```yaml
  eds_eval:
    enabled: false
    write_metrics: true
    save_qualitative: false
    output_dir: ${main.output_dir}/eds_eval
    report_dir: docs/03_evidence/eds_steering
    reward_mode: normal  # valid: normal, zero, shuffled_keypoints, inverted
    shuffle_seed: 0
    max_visual_chunks_per_episode: 2
    save_population_cloud: true
    save_per_iter_best: true
    save_initial_vs_final: true
```

- [ ] **Step 2: Create metrics module**

Create `core/eds_eval_metrics.py` with:

```python
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import median
from typing import Any


@dataclass
class EDSIterMetrics:
    iter_idx: int
    n_trunc_steps: int
    best_idx: int
    best_cost: float
    best_reward: float
    mean_reward: float
    reward_spread: float
    score_entropy: float
    unique_parent_ratio: float
    population_diversity: float


@dataclass
class EDSChunkMetrics:
    episode: int | None = None
    global_step: int | None = None
    task_id: int | None = None
    suite: str | None = None
    guidance_type: str = "eds"
    reward_mode: str = "normal"
    population_size: int = 0
    cem_iters: int = 0
    use_cem: bool = False
    temperature: float = 0.0
    eds_enter_count: int = 0
    score_call_count: int = 0
    resample_count: int = 0
    renoise_count: int = 0
    rollout_count: int = 0
    population_size_observed: int = 0
    population_shape: list[int] = field(default_factory=list)
    score_shape: list[int] = field(default_factory=list)
    initial_best_reward: float | None = None
    final_best_reward: float | None = None
    initial_mean_reward: float | None = None
    final_mean_reward: float | None = None
    reward_spread: float | None = None
    selected_reward: float | None = None
    selected_cost: float | None = None
    selected_idx: int | None = None
    score_entropy: float | None = None
    unique_parent_ratio_mean: float | None = None
    population_diversity_initial: float | None = None
    population_diversity_final: float | None = None
    target_distance_before: float | None = None
    target_distance_after: float | None = None
    action_mask_violation_max: float = 0.0
    nonfinite_count: int = 0
    select_action_latency_s: float | None = None
    eds_loop_latency_s: float | None = None
    per_iter: list[EDSIterMetrics] = field(default_factory=list)

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        return []
    return [
        json.loads(line)
        for line in input_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def finite_or_none(value: float | int | None) -> float | None:
    if value is None:
        return None
    value_f = float(value)
    return value_f if math.isfinite(value_f) else None


def wilson_ci(success: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return (0.0, 0.0)
    phat = success / total
    denom = 1.0 + z * z / total
    center = (phat + z * z / (2.0 * total)) / denom
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * total)) / total) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def summarize_latency(records: list[dict[str, Any]], key: str) -> dict[str, float | None]:
    values = sorted(
        float(record[key])
        for record in records
        if record.get(key) is not None and math.isfinite(float(record[key]))
    )
    if not values:
        return {"p50": None, "p95": None, "mean": None}
    p95_idx = min(len(values) - 1, math.ceil(0.95 * len(values)) - 1)
    return {
        "p50": float(median(values)),
        "p95": float(values[p95_idx]),
        "mean": float(sum(values) / len(values)),
    }
```

- [ ] **Step 3: Add metrics unit tests**

Create `tests/test_eds_eval_metrics.py` with:

```python
import json

from core.eds_eval_metrics import (
    EDSChunkMetrics,
    EDSIterMetrics,
    append_jsonl,
    read_jsonl,
    summarize_latency,
    wilson_ci,
)


def test_eds_chunk_metrics_serializes_nested_iter_metrics():
    metrics = EDSChunkMetrics(
        population_size=16,
        cem_iters=10,
        eds_enter_count=1,
        per_iter=[
            EDSIterMetrics(
                iter_idx=0,
                n_trunc_steps=5,
                best_idx=3,
                best_cost=0.2,
                best_reward=-0.2,
                mean_reward=-0.5,
                reward_spread=0.3,
                score_entropy=2.1,
                unique_parent_ratio=0.5,
                population_diversity=0.01,
            )
        ],
    )

    payload = metrics.to_jsonable()

    assert payload["population_size"] == 16
    assert payload["per_iter"][0]["iter_idx"] == 0
    json.dumps(payload)


def test_append_and_read_jsonl_round_trip(tmp_path):
    path = tmp_path / "eds_metrics.jsonl"

    append_jsonl(path, {"episode": 1, "selected_idx": 2})
    append_jsonl(path, {"episode": 2, "selected_idx": 0})

    assert read_jsonl(path) == [
        {"episode": 1, "selected_idx": 2},
        {"episode": 2, "selected_idx": 0},
    ]


def test_wilson_ci_has_reasonable_bounds():
    low, high = wilson_ci(success=8, total=10)

    assert 0.0 <= low < 0.8 < high <= 1.0


def test_summarize_latency_reports_p50_p95_mean():
    summary = summarize_latency(
        [
            {"select_action_latency_s": 1.0},
            {"select_action_latency_s": 2.0},
            {"select_action_latency_s": 3.0},
        ],
        "select_action_latency_s",
    )

    assert summary["p50"] == 2.0
    assert summary["p95"] == 3.0
    assert summary["mean"] == 2.0
```

- [ ] **Step 4: Run tests**

Run:

```bash
pytest tests/test_eds_eval_metrics.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add configs/config.yaml core/eds_eval_metrics.py tests/test_eds_eval_metrics.py
git commit -m "eval: add EDS metrics schema"
```

---

### Task 2: Instrument RDTSteer EDS Loop And Reward Ablations

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Extend `_EDSConfig`**

In `core/rdt_policy_steer.py`, extend `_EDSConfig`:

```python
@dataclass(frozen=True)
class _EDSConfig:
    population_size: int = 16
    use_cem: bool = False
    cem_iters: int = 20
    num_elites: int = 32
    temperature: float = 0.1
    initial_population_cache: Optional[str] = None
    ed_population_cache: Optional[str] = None
    use_initial_cache: bool = False
    save_initial_cache: bool = False
    save_ed_cache: bool = False
    reward_mode: str = "normal"
    shuffle_seed: int = 0
```

In `_resolve_eds_config_with_reference_defaults()`, add:

```python
            reward_mode=str(cfg.get("reward_mode", "normal")),
            shuffle_seed=int(cfg.get("shuffle_seed", 0)),
```

Then validate:

```python
        if resolved.reward_mode not in {"normal", "zero", "shuffled_keypoints", "inverted"}:
            raise ValueError(
                "EDS reward_mode must be one of normal, zero, shuffled_keypoints, inverted"
            )
```

- [ ] **Step 2: Add trace storage fields**

Import metrics at the top of `core/rdt_policy_steer.py`:

```python
import time
from core.eds_eval_metrics import EDSChunkMetrics, EDSIterMetrics
```

In `reset()`, add:

```python
        self._last_eds_metrics = None
        self._last_eds_artifacts = None
```

Add public getters near `get_last_visualization_action_candidates()`:

```python
    def get_last_eds_metrics(self) -> Optional[dict]:
        if self._last_eds_metrics is None:
            return None
        return dict(self._last_eds_metrics)

    def get_last_eds_artifacts(self) -> Optional[dict]:
        if self._last_eds_artifacts is None:
            return None
        return dict(self._last_eds_artifacts)
```

- [ ] **Step 3: Implement reward ablation scoring**

Change `_eds_score_population_as_cost()` signature:

```python
    def _eds_score_population_as_cost(
        self,
        samples: Tensor,
        *,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        reward_mode: str = "normal",
        shuffle_seed: int = 0,
    ) -> tuple[Tensor, dict]:
```

Replace its body with:

```python
        scoring_keypoints = keypoints
        if reward_mode == "shuffled_keypoints" and keypoints is not None and keypoints.shape[0] > 1:
            generator = torch.Generator(device=keypoints.device)
            generator.manual_seed(int(shuffle_seed))
            perm = torch.randperm(keypoints.shape[0], generator=generator, device=keypoints.device)
            scoring_keypoints = keypoints.index_select(0, perm)

        rewards = self._score_particles(
            samples,
            scoring_keypoints,
            guidance_fns,
            slice_kind="eds",
        )
        if reward_mode == "zero":
            rewards = torch.zeros_like(rewards)
        elif reward_mode == "inverted":
            rewards = -rewards
        elif reward_mode not in {"normal", "shuffled_keypoints"}:
            raise ValueError(f"Unsupported EDS reward_mode={reward_mode!r}")

        costs = -rewards
        return costs.detach(), {"rewards": rewards.detach()}
```

Update all call sites to pass `reward_mode=cfg.reward_mode` and `shuffle_seed=cfg.shuffle_seed`.

- [ ] **Step 4: Add metric helper methods**

Add these methods in `RDTSteer` before `_eds_guided_denoise_loop()`:

```python
    def _eds_population_diversity(self, population: Tensor) -> float:
        flat = population.detach().reshape(population.shape[0], -1)
        if flat.shape[0] <= 1:
            return 0.0
        distances = torch.pdist(flat.float(), p=2)
        if distances.numel() == 0:
            return 0.0
        return float(distances.mean().detach().cpu().item())

    def _eds_score_entropy(self, costs: Tensor, temperature: float) -> float:
        probs = self._eds_sampling_probabilities_from_cost(costs, temperature)
        entropy = -(probs * torch.log(probs.clamp_min(1e-12))).sum()
        return float(entropy.detach().cpu().item())

    def _eds_target_distance(self, samples: Tensor, keypoints: Optional[Tensor], idx: int) -> Optional[float]:
        if keypoints is None or keypoints.numel() == 0:
            return None
        trajs = self._trajectory_reward_slice(
            self._rdt_sample_to_trajectory_3d(samples),
            "eds",
        )
        selected_final = trajs[int(idx), -1, :3]
        target = keypoints.reshape(-1, keypoints.shape[-1])[0, :3].to(
            device=selected_final.device,
            dtype=selected_final.dtype,
        )
        distance = torch.linalg.norm(selected_final - target)
        return float(distance.detach().cpu().item())

    def _eds_action_mask_violation(self, population: Tensor, cond: dict) -> float:
        mask = self._expand_action_mask_for_population(cond["action_mask"], population)
        violation = torch.abs(population * (1.0 - mask)).max()
        return float(violation.detach().cpu().item())
```

- [ ] **Step 5: Record counters and selected-best metrics**

Inside `_eds_guided_denoise_loop()`, initialize a metrics object immediately after `cfg = eds_config`:

```python
        loop_start = time.perf_counter()
        metrics = EDSChunkMetrics(
            guidance_type="eds",
            reward_mode=cfg.reward_mode,
            population_size=cfg.population_size,
            cem_iters=cfg.cem_iters,
            use_cem=cfg.use_cem,
            temperature=cfg.temperature,
            eds_enter_count=1,
        )
        artifact_iters: list[dict] = []
```

After initial scoring, set:

```python
        initial_best_idx = int(torch.argmin(population_scores).item())
        initial_rewards = -population_scores.detach()
        metrics.score_call_count = 1
        metrics.population_size_observed = int(population.shape[0])
        metrics.population_shape = list(population.shape)
        metrics.score_shape = list(population_scores.shape)
        metrics.initial_best_reward = float(initial_rewards.max().detach().cpu().item())
        metrics.initial_mean_reward = float(initial_rewards.mean().detach().cpu().item())
        metrics.population_diversity_initial = self._eds_population_diversity(population)
        metrics.target_distance_before = self._eds_target_distance(
            population,
            keypoints,
            initial_best_idx,
        )
        initial_action_candidates = self._decode_visualization_action_candidates(population).detach().cpu()
```

In the resampling branch, record the parent diversity:

```python
            unique_parent_ratio = float(indices.unique().numel()) / float(cfg.population_size)
            metrics.resample_count += 1
```

After renoise:

```python
            metrics.renoise_count += 1
```

After rollout and score validation:

```python
            metrics.rollout_count += 1
            metrics.score_call_count += 1
            iter_rewards = -population_scores.detach()
            iter_best_idx = int(torch.argmin(population_scores).item())
            metrics.per_iter.append(
                EDSIterMetrics(
                    iter_idx=i,
                    n_trunc_steps=n_trunc_steps,
                    best_idx=iter_best_idx,
                    best_cost=float(population_scores[iter_best_idx].detach().cpu().item()),
                    best_reward=float(iter_rewards[iter_best_idx].detach().cpu().item()),
                    mean_reward=float(iter_rewards.mean().detach().cpu().item()),
                    reward_spread=float((iter_rewards.max() - iter_rewards.mean()).detach().cpu().item()),
                    score_entropy=self._eds_score_entropy(population_scores, cfg.temperature),
                    unique_parent_ratio=unique_parent_ratio,
                    population_diversity=self._eds_population_diversity(population),
                )
            )
            artifact_iters.append(
                {
                    "iter_idx": i,
                    "actions": self._decode_visualization_action_candidates(population).detach().cpu(),
                    "scores": population_scores.detach().cpu(),
                }
            )
```

After final `best_idx` selection, set:

```python
        final_rewards = -population_scores.detach()
        metrics.final_best_reward = float(final_rewards.max().detach().cpu().item())
        metrics.final_mean_reward = float(final_rewards.mean().detach().cpu().item())
        metrics.reward_spread = float((final_rewards.max() - final_rewards.mean()).detach().cpu().item())
        metrics.selected_idx = best_idx
        metrics.selected_cost = float(population_scores[best_idx].detach().cpu().item())
        metrics.selected_reward = float(final_rewards[best_idx].detach().cpu().item())
        metrics.population_diversity_final = self._eds_population_diversity(population)
        metrics.target_distance_after = self._eds_target_distance(population, keypoints, best_idx)
        metrics.action_mask_violation_max = self._eds_action_mask_violation(population, cond)
        metrics.nonfinite_count = int((~torch.isfinite(population)).sum().detach().cpu().item())
        metrics.eds_loop_latency_s = float(time.perf_counter() - loop_start)
        if metrics.per_iter:
            metrics.score_entropy = metrics.per_iter[-1].score_entropy
            metrics.unique_parent_ratio_mean = float(
                sum(item.unique_parent_ratio for item in metrics.per_iter) / len(metrics.per_iter)
            )
        self._last_eds_metrics = metrics.to_jsonable()
        self._last_eds_artifacts = {
            "initial_actions": initial_action_candidates,
            "final_actions": self._decode_visualization_action_candidates(population).detach().cpu(),
            "final_scores": population_scores.detach().cpu(),
            "selected_idx": best_idx,
            "per_iter": artifact_iters,
        }
```

- [ ] **Step 6: Add RDTSteer tests**

Append to `tests/test_rdt_steer.py`:

```python
def test_eds_loop_records_deployment_counters(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 2, "temperature": 0.1},
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics["eds_enter_count"] == 1
    assert metrics["score_call_count"] == 3
    assert metrics["resample_count"] == 2
    assert metrics["renoise_count"] == 2
    assert metrics["rollout_count"] == 2
    assert metrics["population_shape"] == [3, 64, 128]
    assert metrics["score_shape"] == [3]
    assert metrics["selected_idx"] is not None


def test_eds_zero_reward_records_no_reward_spread(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "reward_mode": "zero",
        },
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics["reward_mode"] == "zero"
    assert metrics["initial_best_reward"] == 0.0
    assert metrics["final_best_reward"] == 0.0
    assert metrics["reward_spread"] == 0.0
```

- [ ] **Step 7: Run tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_loop_records_deployment_counters tests/test_rdt_steer.py::test_eds_zero_reward_records_no_reward_spread -q
```

Expected: both tests pass.

- [ ] **Step 8: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "eval: instrument RDT EDS loop"
```

---

### Task 3: Write Runtime Metrics From Main

**Files:**
- Modify: `main.py`
- Modify: `tests/test_main_rdt_startup.py`

- [ ] **Step 1: Add imports**

In `main.py`, add:

```python
import time
from pathlib import Path
from core.eds_eval_metrics import append_jsonl
```

- [ ] **Step 2: Time policy selection and write JSONL**

Immediately before `action_chunk = self.policy.select_action(**select_kwargs)`, add:

```python
            select_action_start_s = time.perf_counter()
```

Immediately after the call, add:

```python
            select_action_latency_s = float(time.perf_counter() - select_action_start_s)
            eds_eval_config = _config_section_to_dict(self.config.get("eds_eval"), "main.eds_eval")
            if (
                generate_new_chunk
                and guidance_type == "eds"
                and eds_eval_config.get("enabled", False)
                and eds_eval_config.get("write_metrics", True)
                and hasattr(self.policy, "get_last_eds_metrics")
            ):
                eds_metrics = self.policy.get_last_eds_metrics()
                if eds_metrics is not None:
                    eds_metrics.update(
                        {
                            "episode": getattr(self, "current_episode", None),
                            "global_step": int(global_steps),
                            "suite": getattr(self.adapter, "suite_name", None),
                            "task_id": getattr(self.adapter, "current_task_idx", None),
                            "select_action_latency_s": select_action_latency_s,
                        }
                    )
                    metrics_path = Path(
                        eds_eval_config.get("output_dir", self.output_dir)
                    ) / "eds_metrics.jsonl"
                    append_jsonl(metrics_path, eds_metrics)
```

- [ ] **Step 3: Pass reward mode into EDS config**

After `eds_config = _config_section_to_dict(...)`, add:

```python
            eds_eval_config = _config_section_to_dict(self.config.get("eds_eval"), "main.eds_eval")
            if eds_eval_config:
                eds_config["reward_mode"] = eds_eval_config.get("reward_mode", eds_config.get("reward_mode", "normal"))
                eds_config["shuffle_seed"] = eds_eval_config.get("shuffle_seed", eds_config.get("shuffle_seed", 0))
```

Remove the duplicate `eds_eval_config = ...` line from Step 2 if both blocks are in the same scope.

- [ ] **Step 4: Add unit test for JSONL writing helper path**

Append to `tests/test_main_rdt_startup.py`:

```python
def test_main_can_append_eds_metrics_jsonl(tmp_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from core.eds_eval_metrics import append_jsonl, read_jsonl

    metrics_path = tmp_path / "eds_eval" / "eds_metrics.jsonl"

    append_jsonl(
        metrics_path,
        {
            "guidance_type": "eds",
            "eds_enter_count": 1,
            "select_action_latency_s": 1.25,
        },
    )

    rows = read_jsonl(metrics_path)

    assert rows == [
        {
            "guidance_type": "eds",
            "eds_enter_count": 1,
            "select_action_latency_s": 1.25,
        }
    ]
```

- [ ] **Step 5: Run checks**

Run:

```bash
python -m py_compile main.py
pytest tests/test_main_rdt_startup.py::test_main_can_append_eds_metrics_jsonl -q
```

Expected: compile succeeds and test passes.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_main_rdt_startup.py
git commit -m "eval: write EDS runtime metrics"
```

---

### Task 4: Add Qualitative Artifact Saving

**Files:**
- Create: `utils/eds_eval_vis.py`
- Modify: `main.py`
- Test: `tests/test_eds_eval_metrics.py`

- [ ] **Step 1: Create visualization utilities**

Create `utils/eds_eval_vis.py` with:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import imageio.v2 as imageio
import numpy as np
import torch

from utils.vis_utils import draw_action_trajectory_on_vlm_image, draw_keypoints_on_image


def _to_action_candidates(tensor: Any) -> torch.Tensor:
    if torch.is_tensor(tensor):
        return tensor.detach().cpu().float()
    return torch.as_tensor(tensor, dtype=torch.float32)


def save_image(path: str | Path, image: np.ndarray) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    imageio.imwrite(output_path, np.asarray(image).astype(np.uint8))


def save_side_by_side(path: str | Path, left: np.ndarray, right: np.ndarray, labels: tuple[str, str]) -> None:
    left_img = np.asarray(left).copy()
    right_img = np.asarray(right).copy()
    cv2.putText(left_img, labels[0], (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    cv2.putText(right_img, labels[1], (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    save_image(path, np.concatenate([left_img, right_img], axis=1))


def draw_population_cloud(adapter, population_actions: torch.Tensor, max_particles: int = 16) -> np.ndarray:
    candidates = _to_action_candidates(population_actions)
    if candidates.ndim == 2:
        candidates = candidates.unsqueeze(0)
    candidates = candidates[:max_particles]
    return draw_action_trajectory_on_vlm_image(
        adapter=adapter,
        action_chunk=candidates,
        num_steps=min(16, candidates.shape[1]),
        global_step=0,
        action_executed=0,
    )


def save_eds_qualitative_artifacts(
    *,
    output_dir: str | Path,
    adapter,
    keypoints: np.ndarray | None,
    mask_ids,
    artifacts: dict[str, Any],
    episode: int,
    global_step: int,
    max_iters: int = 10,
) -> list[str]:
    output_root = Path(output_dir) / f"episode_{episode:03d}" / f"chunk_{global_step:06d}"
    output_root.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    if keypoints is not None:
        image = np.array(adapter.get_vlm_image())
        try:
            image = draw_keypoints_on_image(adapter=adapter, image=image, keypoints=keypoints, mask_ids=mask_ids)
        except Exception:
            image = np.array(adapter.get_vlm_image())
        path = output_root / "keypoints_projected.png"
        save_image(path, image)
        saved.append(str(path))

    final_actions = artifacts.get("final_actions")
    selected_idx = int(artifacts.get("selected_idx", 0))
    if final_actions is not None:
        final_actions = _to_action_candidates(final_actions)
        selected = final_actions[selected_idx : selected_idx + 1]
        selected_img = draw_action_trajectory_on_vlm_image(
            adapter=adapter,
            action_chunk=selected,
            num_steps=min(16, selected.shape[1]),
            global_step=global_step,
            action_executed=0,
        )
        path = output_root / "keypoints_selected_eef_overlay.png"
        save_image(path, selected_img)
        saved.append(str(path))

        cloud = draw_population_cloud(adapter, final_actions)
        path = output_root / "population_overlay_iter_last.png"
        save_image(path, cloud)
        saved.append(str(path))

    initial_actions = artifacts.get("initial_actions")
    if initial_actions is not None and final_actions is not None:
        initial_actions = _to_action_candidates(initial_actions)
        initial_best = initial_actions[0:1]
        final_selected = final_actions[selected_idx : selected_idx + 1]
        left = draw_action_trajectory_on_vlm_image(
            adapter=adapter,
            action_chunk=initial_best,
            num_steps=min(16, initial_best.shape[1]),
            global_step=global_step,
            action_executed=0,
        )
        right = draw_action_trajectory_on_vlm_image(
            adapter=adapter,
            action_chunk=final_selected,
            num_steps=min(16, final_selected.shape[1]),
            global_step=global_step,
            action_executed=0,
        )
        path = output_root / "initial_best_vs_final_selected.png"
        save_side_by_side(path, left, right, ("initial best", "final selected"))
        saved.append(str(path))

    for item in artifacts.get("per_iter", [])[:max_iters]:
        iter_idx = int(item["iter_idx"])
        population = _to_action_candidates(item["actions"])
        scores = _to_action_candidates(item["scores"]).reshape(-1)
        best_idx = int(torch.argmin(scores).item())
        best = population[best_idx : best_idx + 1]
        best_img = draw_action_trajectory_on_vlm_image(
            adapter=adapter,
            action_chunk=best,
            num_steps=min(16, best.shape[1]),
            global_step=global_step,
            action_executed=0,
        )
        path = output_root / f"best_trajectory_overlay_iter_{iter_idx:03d}.png"
        save_image(path, best_img)
        saved.append(str(path))

        cloud_img = draw_population_cloud(adapter, population)
        path = output_root / f"population_cloud_iter_{iter_idx:03d}.png"
        save_image(path, cloud_img)
        saved.append(str(path))

    return saved
```

- [ ] **Step 2: Call visualization from `main.py` before JSONL append**

Import:

```python
from utils.eds_eval_vis import save_eds_qualitative_artifacts
```

Replace the Task 3 JSONL metrics write block with this version so qualitative artifact paths are included in the JSONL record:

```python
            select_action_latency_s = float(time.perf_counter() - select_action_start_s)
            if (
                generate_new_chunk
                and guidance_type == "eds"
                and eds_eval_config.get("enabled", False)
                and eds_eval_config.get("write_metrics", True)
                and hasattr(self.policy, "get_last_eds_metrics")
            ):
                eds_metrics = self.policy.get_last_eds_metrics()
                if eds_metrics is not None:
                    eds_metrics.update(
                        {
                            "episode": getattr(self, "current_episode", None),
                            "global_step": int(global_steps),
                            "suite": getattr(self.adapter, "suite_name", None),
                            "task_id": getattr(self.adapter, "current_task_idx", None),
                            "select_action_latency_s": select_action_latency_s,
                        }
                    )
                    if (
                        eds_eval_config.get("save_qualitative", False)
                        and hasattr(self.policy, "get_last_eds_artifacts")
                    ):
                        artifacts = self.policy.get_last_eds_artifacts()
                        if artifacts is not None:
                            visual_root = Path(
                                eds_eval_config.get("output_dir", self.output_dir)
                            ) / "qualitative"
                            saved_artifacts = save_eds_qualitative_artifacts(
                                output_dir=visual_root,
                                adapter=self.adapter,
                                keypoints=keypoints,
                                mask_ids=mask_ids,
                                artifacts=artifacts,
                                episode=getattr(self, "current_episode", 0) or 0,
                                global_step=int(global_steps),
                                max_iters=int(eds_eval_config.get("max_visual_chunks_per_episode", 2)),
                            )
                            if saved_artifacts:
                                eds_metrics["qualitative_artifacts"] = saved_artifacts
                    metrics_path = Path(
                        eds_eval_config.get("output_dir", self.output_dir)
                    ) / "eds_metrics.jsonl"
                    append_jsonl(metrics_path, eds_metrics)
```

- [ ] **Step 3: Add visualization smoke test**

Append to `tests/test_eds_eval_metrics.py`:

```python
def test_eds_qualitative_save_image_creates_parent_dirs(tmp_path):
    import numpy as np
    from utils.eds_eval_vis import save_image

    path = tmp_path / "qualitative" / "episode_000" / "frame.png"
    image = np.zeros((8, 8, 3), dtype=np.uint8)

    save_image(path, image)

    assert path.exists()
```

- [ ] **Step 4: Run checks**

Run:

```bash
python -m py_compile utils/eds_eval_vis.py main.py
pytest tests/test_eds_eval_metrics.py::test_eds_qualitative_save_image_creates_parent_dirs -q
```

Expected: compile succeeds and test passes.

- [ ] **Step 5: Commit**

```bash
git add utils/eds_eval_vis.py main.py tests/test_eds_eval_metrics.py
git commit -m "eval: save EDS qualitative artifacts"
```

---

### Task 5: Build RDT+EDS-Only Evaluation Runner

**Files:**
- Create: `scripts/rdt_eds_eval_runner.py`
- Create: `scripts/run_rdt_eds_eval.sh`
- Test: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Create runner with restricted scope**

Create `scripts/rdt_eds_eval_runner.py` with these top-level constants and helpers:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = WORKTREE_ROOT / "docs" / "03_evidence" / "eds_steering"
RUN_ROOT = WORKTREE_ROOT / "outputs" / "rdt_eds_eval"
STATUS_CSV = EVIDENCE_ROOT / "rdt_eds_eval_status.csv"
BASE_SUITE = "libero_object"
OOD_SUITES = [
    "libero_object_object",
    "libero_object_swap",
    "libero_object_lan",
    "libero_object_task",
    "libero_object_env",
    "libero_object_temp",
]
METHODS = [
    {"method": "unguided", "label": "unguided"},
    {"method": "eds", "label": "eds_p16_c10", "population_size": 16, "cem_iters": 10, "use_cem": False, "reward_mode": "normal"},
    {"method": "eds", "label": "eds_p16_c20", "population_size": 16, "cem_iters": 20, "use_cem": False, "reward_mode": "normal"},
    {"method": "eds", "label": "eds_p32_c10", "population_size": 32, "cem_iters": 10, "use_cem": False, "reward_mode": "normal"},
    {"method": "eds", "label": "eds_p32_c10_cem", "population_size": 32, "cem_iters": 10, "use_cem": True, "reward_mode": "normal"},
    {"method": "eds", "label": "eds_zero", "population_size": 16, "cem_iters": 10, "use_cem": False, "reward_mode": "zero"},
    {"method": "eds", "label": "eds_shuffled", "population_size": 16, "cem_iters": 10, "use_cem": False, "reward_mode": "shuffled_keypoints"},
    {"method": "eds", "label": "eds_inverted", "population_size": 16, "cem_iters": 10, "use_cem": False, "reward_mode": "inverted"},
]


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    RUN_ROOT.mkdir(parents=True, exist_ok=True)


def build_jobs(level: str, episodes: int) -> list[dict[str, object]]:
    if level == "level3":
        suites = [BASE_SUITE]
        methods = METHODS
    elif level == "level4":
        suites = OOD_SUITES
        methods = METHODS[:5] + METHODS[5:]
    else:
        raise ValueError(f"Unsupported online level: {level}")

    jobs: list[dict[str, object]] = []
    for suite in suites:
        for method in methods:
            job_id = f"{level}_{suite}_{method['label']}"
            jobs.append(
                {
                    "job_id": job_id,
                    "level": level,
                    "suite": suite,
                    "episodes": episodes,
                    **method,
                }
            )
    return jobs


def build_main_command(job: dict[str, object], gpu: str, timeout_seconds: int) -> list[str]:
    output_dir = RUN_ROOT / str(job["job_id"])
    args = [
        "timeout",
        str(timeout_seconds),
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        "policy.type=rdt",
        f"backend.libero.suite_name={job['suite']}",
        f"main.episode_num={job['episodes']}",
        "main.use_vlm_stage_recognition=true",
        "perception.gemini_grounding.enabled=true",
        "main.render=false",
        "main.visualize_trajectory=true",
        "main.debug_draw_trajectory=true",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=true",
        f"main.eds_eval.output_dir={output_dir / 'eds_eval'}",
        f"hydra.run.dir={output_dir}",
    ]
    if job["method"] == "unguided":
        args.extend(["main.use_guidance=false"])
    else:
        args.extend(
            [
                "main.use_guidance=true",
                "main.guidance_type=eds",
                f"main.eds_config.population_size={job['population_size']}",
                f"main.eds_config.cem_iters={job['cem_iters']}",
                f"main.eds_config.use_cem={str(job['use_cem']).lower()}",
                f"main.eds_eval.reward_mode={job['reward_mode']}",
            ]
        )
    return args
```

- [ ] **Step 2: Add preflight checks**

Add:

```python
def preflight() -> int:
    ensure_dirs()
    failures: list[str] = []
    required_paths = [
        WORKTREE_ROOT / "configs" / "config.yaml",
        WORKTREE_ROOT / "core" / "rdt_policy_steer.py",
    ]
    for path in required_paths:
        if not path.exists():
            failures.append(f"missing required path: {path}")

    libero_pro = WORKTREE_ROOT / "third_party" / "libero_pro"
    if not (libero_pro / "perturbation.py").exists():
        failures.append("missing third_party/libero_pro/perturbation.py")
    if not (libero_pro / "evaluation_config.yaml").exists():
        failures.append("missing third_party/libero_pro/evaluation_config.yaml")

    report = EVIDENCE_ROOT / "preflight.md"
    report.write_text(
        "# RDT+EDS Evaluation Preflight\n\n"
        + f"Timestamp: `{now_iso()}`\n\n"
        + ("Status: `pass`\n" if not failures else "Status: `blocked`\n\n")
        + "\n".join(f"- {failure}" for failure in failures)
        + "\n",
        encoding="utf-8",
    )
    return 0 if not failures else 2
```

- [ ] **Step 3: Add status CSV and command writer**

Add:

```python
def write_status(rows: list[dict[str, object]]) -> None:
    ensure_dirs()
    fields = [
        "job_id",
        "level",
        "suite",
        "method",
        "label",
        "status",
        "episodes",
        "output_dir",
        "log_file",
    ]
    with STATUS_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def init(level: str, episodes: int) -> int:
    jobs = build_jobs(level, episodes)
    rows = []
    for job in jobs:
        rows.append(
            {
                **job,
                "status": "pending",
                "output_dir": str(RUN_ROOT / str(job["job_id"])),
                "log_file": str(EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log"),
            }
        )
    write_status(rows)
    return 0
```

- [ ] **Step 4: Add CLI**

Add:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preflight")
    init_parser = sub.add_parser("init")
    init_parser.add_argument("--level", choices=["level3", "level4"], required=True)
    init_parser.add_argument("--episodes", type=int, default=10)
    command_parser = sub.add_parser("print-command")
    command_parser.add_argument("--level", choices=["level3", "level4"], required=True)
    command_parser.add_argument("--episodes", type=int, default=10)
    command_parser.add_argument("--job-index", type=int, default=0)
    command_parser.add_argument("--gpu", default="0")
    command_parser.add_argument("--timeout-seconds", type=int, default=28800)
    args = parser.parse_args()

    if args.cmd == "preflight":
        return preflight()
    if args.cmd == "init":
        return init(args.level, args.episodes)
    if args.cmd == "print-command":
        jobs = build_jobs(args.level, args.episodes)
        command = build_main_command(jobs[args.job_index], args.gpu, args.timeout_seconds)
        print(" ".join(command))
        return 0
    raise ValueError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Create shell wrapper**

Create `scripts/run_rdt_eds_eval.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNER="${SCRIPT_DIR}/rdt_eds_eval_runner.py"
SESSION="${RDT_EDS_EVAL_TMUX_SESSION:-rdt_eds_eval}"

load_local_env() {
  local env_file
  for env_file in "${WORKTREE_ROOT}/.env" "${WORKTREE_ROOT}/.env.local"; do
    if [[ -f "${env_file}" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "${env_file}"
      set +a
    fi
  done
}

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_rdt_eds_eval.sh preflight
  scripts/run_rdt_eds_eval.sh init --level level3 --episodes 10
  scripts/run_rdt_eds_eval.sh start --level level3 --episodes 10 --gpus 0,1,2,3
  scripts/run_rdt_eds_eval.sh attach
USAGE
}

require_keys() {
  [[ -n "${OPENAI_API_KEY:-}" ]] || { echo "BLOCKED: OPENAI_API_KEY missing" >&2; exit 2; }
  [[ -n "${GOOGLE_API_KEY:-}" ]] || { echo "BLOCKED: GOOGLE_API_KEY missing" >&2; exit 2; }
}

load_local_env
cmd="${1:-help}"
shift || true

case "${cmd}" in
  preflight)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" preflight
    ;;
  init)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" init "$@"
    ;;
  start)
    require_keys
    cd "${WORKTREE_ROOT}"
    tmux new-session -d -s "${SESSION}" -c "${WORKTREE_ROOT}" "echo RDT+EDS evaluation session initialized; bash"
    echo "Started tmux session: ${SESSION}"
    echo "Attach: tmux attach -t ${SESSION}"
    ;;
  attach)
    tmux attach -t "${SESSION}"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: ${cmd}" >&2
    usage
    exit 2
    ;;
esac
```

- [ ] **Step 6: Add runner unit tests**

Create `tests/test_eds_eval_runner.py` with:

```python
import importlib.util
from pathlib import Path


def _load_runner():
    path = Path(__file__).resolve().parents[1] / "scripts" / "rdt_eds_eval_runner.py"
    spec = importlib.util.spec_from_file_location("rdt_eds_eval_runner", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runner_level3_is_restricted_to_libero_object_and_no_vls():
    runner = _load_runner()

    jobs = runner.build_jobs("level3", episodes=10)

    assert {job["suite"] for job in jobs} == {"libero_object"}
    assert all(job["method"] != "vls" for job in jobs)
    assert all("pi05" not in job["job_id"] for job in jobs)


def test_runner_level4_uses_only_libero_object_perturbations():
    runner = _load_runner()

    jobs = runner.build_jobs("level4", episodes=10)
    suites = {job["suite"] for job in jobs}

    assert suites == set(runner.OOD_SUITES)
    assert all(suite.startswith("libero_object_") for suite in suites)
    assert "libero_spatial" not in suites
    assert "libero_goal" not in suites
    assert "libero_10" not in suites


def test_build_main_command_uses_rdt_eds_and_metrics_dir():
    runner = _load_runner()
    job = {
        "job_id": "level3_libero_object_eds_p16_c10",
        "suite": "libero_object",
        "episodes": 10,
        "method": "eds",
        "label": "eds_p16_c10",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "reward_mode": "normal",
    }

    cmd = runner.build_main_command(job, gpu="0", timeout_seconds=120)
    command_text = " ".join(cmd)

    assert "policy.type=rdt" in command_text
    assert "main.guidance_type=eds" in command_text
    assert "main.eds_eval.enabled=true" in command_text
    assert "main.eds_config.population_size=16" in command_text
    assert "main.eds_config.cem_iters=10" in command_text
```

- [ ] **Step 7: Run checks**

Run:

```bash
chmod +x scripts/run_rdt_eds_eval.sh scripts/rdt_eds_eval_runner.py
pytest tests/test_eds_eval_runner.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/rdt_eds_eval_runner.py scripts/run_rdt_eds_eval.sh tests/test_eds_eval_runner.py
git commit -m "eval: add RDT EDS evaluation runner"
```

---

### Task 6: Generate Per-Level And Final Reports

**Files:**
- Modify: `scripts/rdt_eds_eval_runner.py`
- Test: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Add report path mapping**

Add to `scripts/rdt_eds_eval_runner.py`:

```python
LEVEL_REPORTS = {
    "level0": "level_0_deployment_correctness.md",
    "level1": "level_1_mechanism_probe.md",
    "level2": "level_2_online_smoke.md",
    "level3": "level_3_libero_object_success.md",
    "level4": "level_4_libero_pro_ood.md",
    "final": "rdt_eds_final_evaluation_report.md",
}
```

- [ ] **Step 2: Add report writer**

Add:

```python
def write_level_report(level: str, verdict: str, evidence: list[str]) -> Path:
    ensure_dirs()
    if level not in LEVEL_REPORTS:
        raise ValueError(f"Unknown report level: {level}")
    path = EVIDENCE_ROOT / LEVEL_REPORTS[level]
    evidence_lines = "\n".join(f"- {item}" for item in evidence)
    path.write_text(
        f"# RDT+EDS {level.upper()} Evaluation Report\n\n"
        f"Timestamp: `{now_iso()}`\n\n"
        f"Verdict: `{verdict}`\n\n"
        "## Evidence\n\n"
        f"{evidence_lines}\n\n"
        "## Analysis\n\n"
        "This report is generated by `scripts/rdt_eds_eval_runner.py`. "
        "A human reviewer must compare the saved metrics, videos, overlays, and failure labels "
        "against `docs/01_specs/rdt_eds_evaluation_protocol.md` before changing the verdict.\n",
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 3: Add final report writer**

Add:

```python
def write_final_report() -> Path:
    ensure_dirs()
    report_paths = [
        EVIDENCE_ROOT / LEVEL_REPORTS[level]
        for level in ["level0", "level1", "level2", "level3", "level4"]
    ]
    lines = [
        "# RDT+EDS Final Evaluation Report",
        "",
        f"Timestamp: `{now_iso()}`",
        "",
        "## Per-Level Reports",
        "",
    ]
    for report in report_paths:
        status = "present" if report.exists() else "missing"
        lines.append(f"- `{report.relative_to(WORKTREE_ROOT)}`: `{status}`")
    lines.extend(
        [
            "",
            "## Final Verdict",
            "",
            "- Deployment correctness: `inconclusive` until Level 0 report passes.",
            "- Algorithm effectiveness: `inconclusive` until Level 1 through Level 4 reports pass or fail with evidence.",
            "",
            "Previous non-`libero_object` OOD results are excluded because they were caused by wrong checkpoint loading.",
        ]
    )
    path = EVIDENCE_ROOT / LEVEL_REPORTS["final"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Wire CLI commands**

Extend `main()`:

```python
    report_parser = sub.add_parser("write-report")
    report_parser.add_argument("--level", choices=["level0", "level1", "level2", "level3", "level4"], required=True)
    report_parser.add_argument("--verdict", choices=["pass", "fail", "blocked", "inconclusive"], required=True)
    report_parser.add_argument("--evidence", action="append", default=[])
    sub.add_parser("write-final-report")
```

Add command handlers:

```python
    if args.cmd == "write-report":
        path = write_level_report(args.level, args.verdict, args.evidence)
        print(path)
        return 0
    if args.cmd == "write-final-report":
        path = write_final_report()
        print(path)
        return 0
```

- [ ] **Step 5: Add report tests**

Append to `tests/test_eds_eval_runner.py`:

```python
def test_level_report_names_match_protocol():
    runner = _load_runner()

    assert runner.LEVEL_REPORTS["level0"] == "level_0_deployment_correctness.md"
    assert runner.LEVEL_REPORTS["level1"] == "level_1_mechanism_probe.md"
    assert runner.LEVEL_REPORTS["level2"] == "level_2_online_smoke.md"
    assert runner.LEVEL_REPORTS["level3"] == "level_3_libero_object_success.md"
    assert runner.LEVEL_REPORTS["level4"] == "level_4_libero_pro_ood.md"
    assert runner.LEVEL_REPORTS["final"] == "rdt_eds_final_evaluation_report.md"
```

- [ ] **Step 6: Run checks**

Run:

```bash
pytest tests/test_eds_eval_runner.py -q
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py write-report --level level0 --verdict inconclusive --evidence "report writer smoke test"
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py write-final-report
```

Expected:

```text
docs/03_evidence/eds_steering/level_0_deployment_correctness.md
docs/03_evidence/eds_steering/rdt_eds_final_evaluation_report.md
```

- [ ] **Step 7: Commit**

```bash
git add scripts/rdt_eds_eval_runner.py tests/test_eds_eval_runner.py docs/03_evidence/eds_steering/level_0_deployment_correctness.md docs/03_evidence/eds_steering/rdt_eds_final_evaluation_report.md
git commit -m "eval: add RDT EDS report generation"
```

---

### Task 7: Add Level-0 And Level-1 Offline Execution Commands

**Files:**
- Modify: `scripts/rdt_eds_eval_runner.py`
- Modify: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Add Level-0 test command helper**

Add:

```python
def level0_command() -> list[str]:
    return [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "pytest",
        "tests/test_rdt_steer.py::test_eds_loop_records_deployment_counters",
        "tests/test_rdt_steer.py::test_eds_zero_reward_records_no_reward_spread",
        "-q",
    ]
```

- [ ] **Step 2: Add Level-1 offline probe command helper**

Add:

```python
def level1_command() -> list[str]:
    return [
        "conda",
        "run",
        "-n",
        "vla-pilot",
        "python",
        "main.py",
        "policy.type=rdt",
        "backend.libero.suite_name=libero_object",
        "main.episode_num=1",
        "backend.libero.max_episode_steps=20",
        "main.use_guidance=true",
        "main.guidance_type=eds",
        "main.eds_config.population_size=16",
        "main.eds_config.cem_iters=10",
        "main.eds_eval.enabled=true",
        "main.eds_eval.write_metrics=true",
        "main.eds_eval.save_qualitative=true",
        "main.eds_eval.reward_mode=normal",
        f"main.eds_eval.output_dir={RUN_ROOT / 'level1_mechanism_probe' / 'normal' / 'eds_eval'}",
        f"hydra.run.dir={RUN_ROOT / 'level1_mechanism_probe' / 'normal'}",
    ]
```

- [ ] **Step 3: Add CLI print commands**

Add parsers:

```python
sub.add_parser("print-level0-command")
sub.add_parser("print-level1-command")
```

Add handlers:

```python
    if args.cmd == "print-level0-command":
        print(" ".join(level0_command()))
        return 0
    if args.cmd == "print-level1-command":
        print(" ".join(level1_command()))
        return 0
```

- [ ] **Step 4: Add command tests**

Append:

```python
def test_level0_command_runs_deployment_counter_tests():
    runner = _load_runner()
    text = " ".join(runner.level0_command())

    assert "test_eds_loop_records_deployment_counters" in text
    assert "test_eds_zero_reward_records_no_reward_spread" in text


def test_level1_command_uses_libero_object_and_eds_only():
    runner = _load_runner()
    text = " ".join(runner.level1_command())

    assert "backend.libero.suite_name=libero_object" in text
    assert "main.guidance_type=eds" in text
    assert "main.eds_eval.save_qualitative=true" in text
    assert "guidance_type=vls" not in text
```

- [ ] **Step 5: Run checks**

Run:

```bash
pytest tests/test_eds_eval_runner.py -q
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py print-level0-command
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py print-level1-command
```

Expected: commands print without errors.

- [ ] **Step 6: Commit**

```bash
git add scripts/rdt_eds_eval_runner.py tests/test_eds_eval_runner.py
git commit -m "eval: add offline EDS evaluation commands"
```

---

### Task 8: Add Detach-Safe Parallel Execution

**Files:**
- Modify: `scripts/rdt_eds_eval_runner.py`
- Modify: `scripts/run_rdt_eds_eval.sh`
- Modify: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Add job execution helpers**

In `scripts/rdt_eds_eval_runner.py`, add:

```python
def run_job(job: dict[str, object], gpu: str, timeout_seconds: int) -> dict[str, object]:
    output_dir = RUN_ROOT / str(job["job_id"])
    log_dir = EVIDENCE_ROOT / "logs"
    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{job['job_id']}.log"
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("OPENAI_BASE_URL", "https://api.poe.com/v1")
    command = build_main_command(job, gpu=gpu, timeout_seconds=timeout_seconds)

    start = now_iso()
    with log_file.open("a", encoding="utf-8", buffering=1) as f:
        f.write(f"===== START {job['job_id']} {start} GPU={gpu} =====\n")
        f.write("Command: " + " ".join(command) + "\n")
        process = subprocess.run(
            command,
            cwd=str(WORKTREE_ROOT),
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            text=True,
        )
        f.write(f"===== END {job['job_id']} {now_iso()} exit={process.returncode} =====\n")

    results_txt = output_dir / "results.txt"
    status = "done" if process.returncode == 0 and results_txt.exists() else "failed"
    if process.returncode == 124:
        status = "timeout"
    return {
        **job,
        "status": status,
        "output_dir": str(output_dir),
        "log_file": str(log_file),
        "exit_code": process.returncode,
        "start_time": start,
        "end_time": now_iso(),
    }
```

- [ ] **Step 2: Add simple GPU work scheduler**

Add imports near the top of `scripts/rdt_eds_eval_runner.py`:

```python
from queue import Empty, Queue
from threading import Lock, Thread
```

Add:

```python
def run_level(level: str, episodes: int, gpus: str, timeout_seconds: int) -> int:
    ensure_dirs()
    gpu_list = [gpu.strip() for gpu in gpus.split(",") if gpu.strip()]
    if not gpu_list:
        raise SystemExit("No GPUs specified")
    jobs = build_jobs(level, episodes)
    write_status(
        [
            {
                **job,
                "status": "pending",
                "output_dir": str(RUN_ROOT / str(job["job_id"])),
                "log_file": str(EVIDENCE_ROOT / "logs" / f"{job['job_id']}.log"),
            }
            for job in jobs
        ]
    )
    job_queue: Queue[dict[str, object]] = Queue()
    for job in jobs:
        job_queue.put(job)

    rows: list[dict[str, object]] = []
    lock = Lock()

    def worker(gpu: str) -> None:
        while True:
            try:
                job = job_queue.get_nowait()
            except Empty:
                return
            try:
                row = run_job(job, gpu=gpu, timeout_seconds=timeout_seconds)
                with lock:
                    rows.append(row)
                    write_status(rows)
            finally:
                job_queue.task_done()

    threads = [Thread(target=worker, args=(gpu,), daemon=False) for gpu in gpu_list]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    failures = [row for row in rows if row.get("status") != "done"]
    return 0 if not failures else 1
```

This scheduler starts one worker per GPU, so each GPU receives at most one active job at a time. It writes status after each finished job and survives SSH disconnect when launched from tmux.

- [ ] **Step 3: Wire `run-level` CLI**

Add parser:

```python
    run_parser = sub.add_parser("run-level")
    run_parser.add_argument("--level", choices=["level3", "level4"], required=True)
    run_parser.add_argument("--episodes", type=int, default=10)
    run_parser.add_argument("--gpus", default="0")
    run_parser.add_argument("--timeout-seconds", type=int, default=28800)
```

Add handler:

```python
    if args.cmd == "run-level":
        return run_level(args.level, args.episodes, args.gpus, args.timeout_seconds)
```

- [ ] **Step 4: Make tmux start actually run the requested level**

Replace the `start)` case in `scripts/run_rdt_eds_eval.sh` with:

```bash
  start)
    require_keys
    level="level3"
    episodes="10"
    gpus="0"
    timeout_seconds="28800"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --level) level="$2"; shift 2 ;;
        --episodes) episodes="$2"; shift 2 ;;
        --gpus) gpus="$2"; shift 2 ;;
        --timeout-seconds) timeout_seconds="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
      esac
    done
    cd "${WORKTREE_ROOT}"
    if tmux has-session -t "${SESSION}" 2>/dev/null; then
      echo "tmux session already exists: ${SESSION}"
      exit 0
    fi
    tmux new-session -d -s "${SESSION}" -c "${WORKTREE_ROOT}"
    tmux set-environment -t "${SESSION}" OPENAI_API_KEY "${OPENAI_API_KEY}"
    tmux set-environment -t "${SESSION}" GOOGLE_API_KEY "${GOOGLE_API_KEY}"
    tmux set-environment -t "${SESSION}" OPENAI_BASE_URL "${OPENAI_BASE_URL:-https://api.poe.com/v1}"
    tmux send-keys -t "${SESSION}" "cd '${WORKTREE_ROOT}' && conda run -n vla-pilot python '${RUNNER}' run-level --level '${level}' --episodes '${episodes}' --gpus '${gpus}' --timeout-seconds '${timeout_seconds}'" C-m
    echo "Started tmux session: ${SESSION}"
    echo "Attach: tmux attach -t ${SESSION}"
    ;;
```

- [ ] **Step 5: Add runner execution test**

Append to `tests/test_eds_eval_runner.py`:

```python
def test_runner_run_level_cli_is_exposed():
    runner = _load_runner()

    assert hasattr(runner, "run_level")
    assert callable(runner.run_level)
```

- [ ] **Step 6: Run checks**

Run:

```bash
pytest tests/test_eds_eval_runner.py -q
bash -n scripts/run_rdt_eds_eval.sh
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py --help
```

Expected: tests pass, shell syntax is valid, and CLI help prints.

- [ ] **Step 7: Commit**

```bash
git add scripts/rdt_eds_eval_runner.py scripts/run_rdt_eds_eval.sh tests/test_eds_eval_runner.py
git commit -m "eval: add detached RDT EDS evaluation execution"
```

---

### Task 9: End-To-End Verification

**Files:**
- No new files unless verification reports are generated.

- [ ] **Step 1: Run unit tests**

Run:

```bash
pytest \
  tests/test_eds_eval_metrics.py \
  tests/test_eds_eval_runner.py \
  tests/test_rdt_steer.py \
  tests/test_main_rdt_startup.py \
  tests/test_libero_perturbation_parsing.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run static compile checks**

Run:

```bash
python -m py_compile \
  core/eds_eval_metrics.py \
  core/rdt_policy_steer.py \
  main.py \
  scripts/rdt_eds_eval_runner.py \
  utils/eds_eval_vis.py
```

Expected: exit code 0.

- [ ] **Step 3: Run preflight command**

Run:

```bash
scripts/run_rdt_eds_eval.sh preflight
```

Expected:

```text
Status is pass if LIBERO-PRO files exist.
Status is blocked if third_party/libero_pro/perturbation.py or evaluation_config.yaml is missing.
```

If blocked, restore/install LIBERO-PRO before Level 4. Level 0 through Level 3 can still be implemented and tested.

- [ ] **Step 4: Run Level-0 smoke**

Run:

```bash
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py print-level0-command
```

Copy the printed command and execute it.

Expected: the deployment counter tests pass.

- [ ] **Step 5: Generate Level-0 report**

Run:

```bash
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py write-report \
  --level level0 \
  --verdict pass \
  --evidence "EDS route, score, resample, renoise, rollout, finite scores, and zero-reward checks passed in pytest"
```

Expected: `docs/03_evidence/eds_steering/level_0_deployment_correctness.md` exists.

- [ ] **Step 6: Generate final report shell**

Run:

```bash
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py write-final-report
```

Expected: `docs/03_evidence/eds_steering/rdt_eds_final_evaluation_report.md` exists and links per-level report status.

- [ ] **Step 7: Commit verification artifacts**

```bash
git add docs/03_evidence/eds_steering/level_0_deployment_correctness.md docs/03_evidence/eds_steering/rdt_eds_final_evaluation_report.md
git commit -m "eval: verify RDT EDS evaluation harness"
```

---

## Self-Review Checklist

- The plan implements the approved protocol scope: RDT only, EDS only, `libero_object` only for base evaluation, and LIBERO-PRO `libero_object_*` only for OOD.
- The plan excludes RDT+VLS, PI05, `libero_spatial`, `libero_goal`, `libero_10`, and prior bad OOD results.
- Level 0 includes the minimum deployment gate: EDS loop entered, score/resample/renoise/rollout counts match `cem_iters`, population scores finite, selected particle is best-cost particle, and zero-reward behaves like no-op/random selection.
- Level 1 includes reward/progress improvement checks and qualitative overlays.
- Each level writes a separate report, and the final report links them.
- Qualitative artifacts cover keypoints + selected EEF trajectory, per-iteration best trajectory overlays, population clouds, and final selected vs initial best action comparison.
- LIBERO-PRO preflight is explicit and blocking for Level 4 if required files are missing.
