# RBF-Assisted Truncated Rollout EDS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add optional RBF-assisted truncated rollout to EDS, keep baseline behavior unchanged, run the full 128-job level3 rollout-RBF ablation, and write a complete evidence report.

**Architecture:** Keep `_eds_rollout_reference()` as the single rollout entry point and dispatch internally by `truncated_rollout_mode`. Reuse existing 3D EEF RBF diversity gradient machinery from initial RBF sampling, add rollout-specific metrics/trace/visualization, and extend the existing eval runner with a `rollout_rbf_ablation` level.

**Tech Stack:** Python, PyTorch, Hydra, pytest, LIBERO/RDT eval runner, existing EDS mechanism trace and visualization utilities.

---

## Files And Responsibilities

- `core/rdt_policy_steer.py`: `_EDSConfig` fields, config parsing, baseline vs RBF rollout dispatch, rollout telemetry aggregation, trace stage creation.
- `core/eds_eval_metrics.py`: JSON-serializable rollout diversity metrics on `EDSChunkMetrics`.
- `core/eds_mechanism_trace.py`: optional per-stage rollout metadata if required by visualization.
- `utils/eds_mechanism_pretest_vis.py`: rollout-RBF qualitative plots and NPZ/JSON artifacts.
- `scripts/rdt_eds_eval_runner.py`: `rollout_rbf_ablation` job matrix, Hydra overrides, result parser/report writer for rollout metrics.
- `configs/config.yaml`: default rollout diversity config with baseline behavior.
- `tests/test_rdt_steer.py`: config parsing, rollout RBF behavior, fallback, action mask and trace tests.
- `tests/test_eds_eval_metrics.py`: metrics serialization tests.
- `tests/test_eds_mechanism_pretest_vis.py`: rollout RBF artifact tests.
- `tests/test_eds_eval_runner.py`: runner job count, command overrides, report writer tests.
- `docs/03_evidence/eds_init_pg_diverse_sampling/`: final experiment report and logs.

---

### Task 1: Config, Metrics, And Baseline Compatibility

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `core/eds_eval_metrics.py`
- Modify: `configs/config.yaml`
- Test: `tests/test_rdt_steer.py`
- Test: `tests/test_eds_eval_metrics.py`

- [ ] **Step 1: Add failing config parsing tests**

Add tests asserting:

```python
def test_eds_config_accepts_rollout_diversity_fields(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({
        "truncated_rollout_mode": "rbf_diverse",
        "rollout_diversity_scale": 10.0,
        "rollout_diversity_start_ratio": 0.8,
        "rollout_diversity_iters": "all",
        "rollout_diversity_skip_final_steps": 0,
    })
    assert cfg.truncated_rollout_mode == "rbf_diverse"
    assert cfg.rollout_diversity_scale == 10.0
    assert cfg.rollout_diversity_start_ratio == 0.8
    assert cfg.rollout_diversity_iters == "all"
    assert cfg.rollout_diversity_skip_final_steps == 0


def test_eds_config_rejects_invalid_truncated_rollout_mode(stub_steer):
    with pytest.raises(ValueError, match="truncated_rollout_mode"):
        stub_steer._resolve_eds_config_with_reference_defaults({
            "truncated_rollout_mode": "bad",
        })
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_config_accepts_rollout_diversity_fields tests/test_rdt_steer.py::test_eds_config_rejects_invalid_truncated_rollout_mode -q
```

Expected before implementation: fail because fields do not exist.

- [ ] **Step 3: Add config fields and parser**

Add `_EDSConfig` fields:

```python
truncated_rollout_mode: str = "baseline"
rollout_diversity_scale: float = 1.0
rollout_diversity_start_ratio: float = 0.8
rollout_diversity_iters: int | str = 0
rollout_diversity_skip_final_steps: int = 0
```

Parser rules:

- `truncated_rollout_mode in {"baseline", "rbf_diverse"}`;
- scale finite;
- start ratio finite in `[0, 1]`;
- iters is `0`, positive int, or `"all"`;
- skip final steps nonnegative int.

Also add defaults to `configs/config.yaml` under `main.eds_config`, keeping `truncated_rollout_mode: baseline`.

- [ ] **Step 4: Add metrics fields and serialization test**

Add to `EDSChunkMetrics`:

```python
rollout_diversity_enabled: bool = False
rollout_diversity_mode: str = "baseline"
rollout_diversity_scale: float | None = None
rollout_diversity_start_ratio: float | None = None
rollout_diversity_iters_applied: int = 0
rollout_diversity_steps_applied: int = 0
rollout_diversity_grad_norm_mean: float | None = None
rollout_diversity_grad_norm_max: float | None = None
rollout_diversity_fallback_used: bool = False
rollout_diversity_fallback_reason: str | None = None
eef_diversity_before_rollout: float | None = None
eef_diversity_after_rollout_rbf_phase: float | None = None
eef_diversity_after_rollout_final: float | None = None
eef_diversity_rollout_retention_ratio: float | None = None
endpoint_spread_before_rollout: float | None = None
endpoint_spread_after_rollout_rbf_phase: float | None = None
endpoint_spread_after_rollout_final: float | None = None
```

Test `to_jsonable()` preserves these values.

- [ ] **Step 5: Verify baseline compatibility**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_loop_calls_rollout_after_renoise_each_iteration tests/test_eds_eval_metrics.py -q
```

Expected: pass.

---

### Task 2: RBF-Assisted Rollout Algorithm And Trace

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing rollout behavior tests**

Add tests asserting:

- baseline rollout does not call `_compute_diversity_gradient`;
- `truncated_rollout_mode="rbf_diverse"` calls `_compute_diversity_gradient`;
- `rollout_diversity_iters=1` applies only first EDS iteration;
- `rollout_diversity_iters="all"` applies all EDS iterations;
- `renoise_t_max=1`, `rollout_diversity_skip_final_steps=0` still applies diversity;
- nonfinite/None gradient logs warning and falls back to baseline rollout with metrics.

- [ ] **Step 2: Implement helper structure**

Keep `_eds_rollout_reference()` as entry:

```python
def _eds_rollout_reference(..., cfg: _EDSConfig | None = None, iter_idx: int = 0):
    if cfg is None or cfg.truncated_rollout_mode == "baseline":
        return self._eds_rollout_baseline_reference(...)
    if not self._eds_should_apply_rollout_diversity(cfg, iter_idx):
        return self._eds_rollout_baseline_reference(...)
    return self._eds_rollout_rbf_diverse_reference(..., cfg=cfg, iter_idx=iter_idx)
```

Update `_eds_guided_denoise_loop()` call to pass `cfg` and `iter_idx`.

- [ ] **Step 3: Implement rollout RBF step selection**

Use rollout-local timesteps:

```python
rollout_timesteps = scheduler.timesteps[-n_trunc_steps:]
diversity_step_count = math.ceil(len(rollout_timesteps) * cfg.rollout_diversity_start_ratio)
apply if local_step < diversity_step_count
```

`rollout_diversity_skip_final_steps` remains parsed but is `0` by default and not swept.

- [ ] **Step 4: Implement RBF-assisted denoise**

For each selected step:

- DIT forward under `torch.no_grad()`;
- call `_compute_diversity_gradient(x_t)`;
- validate finite gradient;
- mask with `_mask_guidance_gradient()`;
- add to `model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES]` with `RDT_DIVERSITY_SIGN * cfg.rollout_diversity_scale`;
- record grad norms, steps applied, before/after/final snapshots.

Final population must be action-masked before scoring.

- [ ] **Step 5: Add rollout telemetry to metrics**

Aggregate rollout info returned by `_eds_rollout_reference()` into `EDSChunkMetrics`:

- cumulative steps;
- iterations applied;
- grad norm mean/max;
- fallback used/reason;
- first-iteration before/after/final EEF diversity and endpoint spread.

- [ ] **Step 6: Add trace stages**

When trace is enabled, add:

- `rollout_before_diversity`
- `rollout_after_diversity_phase`
- `rollout_final`

Retain existing `after_rollout` and `full_process_after_rollout`.

- [ ] **Step 7: Run core tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected: pass.

---

### Task 3: Rollout RBF Visualization Artifacts

**Files:**
- Modify: `utils/eds_mechanism_pretest_vis.py`
- Modify: `core/eds_mechanism_trace.py` if needed
- Test: `tests/test_eds_mechanism_pretest_vis.py`
- Test: `tests/test_main_rdt_startup.py`

- [ ] **Step 1: Add failing visualization test**

Create a synthetic `EDSMechanismTrace` with rollout RBF stages and assert files are written:

```text
Rollout_RBF_diversity/rollout_eef_3d_before_after_final.png
Rollout_RBF_diversity/rollout_endpoint_scatter_before_after_final.png
Rollout_RBF_diversity/rollout_pairwise_distance_hist_before_after_final.png
Rollout_RBF_diversity/rollout_rbf_diversity_metrics.json
Rollout_RBF_diversity/rollout_rbf_diversity_trace.npz
```

- [ ] **Step 2: Implement artifact writer**

Reuse existing RBF initial diversity plotting style:

- same coordinate axes and view;
- before/after/final trajectories;
- endpoint scatter;
- pairwise distance histogram;
- JSON metrics;
- NPZ arrays.

- [ ] **Step 3: Wire artifact writer into mechanism pretest output**

When trace contains rollout RBF stages, save rollout artifacts inside each qualitative chunk directory.

- [ ] **Step 4: Run visualization tests**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py -q
```

Expected: pass.

---

### Task 4: Eval Runner And Report Writer

**Files:**
- Modify: `scripts/rdt_eds_eval_runner.py`
- Test: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Add failing runner tests**

Tests:

- `build_jobs("rollout_rbf_ablation", episodes=3)` returns 128 jobs;
- labels include `rt4to1_rollrbf_s5_start06_iter1` and `rt1to1_rollrbf_s20_start08_iterall`;
- every job uses `initial_sampling_mode=rbf_diverse_denoise`, `initial_diversity_scale=20.0`, `initial_diversity_start_ratio=0.8`, `population_size=16`, `use_cem=false`, `num_elites=16`;
- command includes:
  - `main.eds_config.truncated_rollout_mode=rbf_diverse`;
  - `main.eds_config.rollout_diversity_scale=<S>`;
  - `main.eds_config.rollout_diversity_start_ratio=<SR>`;
  - `main.eds_config.rollout_diversity_iters=<I>`;
  - `main.eds_config.rollout_diversity_skip_final_steps=0`;
  - qualitative chunk trace settings.

- [ ] **Step 2: Implement job matrix**

Add `ROLLOUT_RBF_ABLATION_METHODS` for the 128 combinations:

```python
renoise_t_max in [4, 3, 2, 1]
rollout_diversity_scale in [5, 10, 15, 20]
rollout_diversity_start_ratio in [0.6, 0.8]
rollout_diversity_iters in [1, 3, 6, "all"]
```

Add `rollout_rbf_ablation` to CLI choices.

- [ ] **Step 3: Implement command overrides**

Extend `build_main_command()` to add rollout diversity Hydra config for rollout RBF jobs.

- [ ] **Step 4: Implement report writer**

Add a report writer that produces:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/YYYY-MM-DD-rollout-rbf-level3-parameter-sweep.md
```

Report must include job status, baseline references, rollout metrics, safety, utility, latency, qualitative artifact counts, top settings, and recommendations.

- [ ] **Step 5: Run runner tests**

Run:

```bash
pytest tests/test_eds_eval_runner.py -q
```

Expected: pass.

---

### Task 5: Full Verification And Experiment Execution

**Files:**
- No new code files unless bug fixes are required.
- Write: `docs/03_evidence/eds_init_pg_diverse_sampling/YYYY-MM-DD-rollout-rbf-level3-parameter-sweep.md`

- [ ] **Step 1: Run required test suite**

Run:

```bash
pytest tests/test_rdt_steer.py tests/test_eds_eval_metrics.py tests/test_eds_eval_runner.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py -q
```

Expected: pass.

- [ ] **Step 2: Print command sanity check**

Run:

```bash
python scripts/rdt_eds_eval_runner.py print-command --level rollout_rbf_ablation --episodes 3 --job-index 0 --gpu 0 --timeout-seconds 28800 --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent --offline-vlm
```

Expected: command includes rollout RBF overrides and qualitative chunk settings.

- [ ] **Step 3: Check GPUs**

Run:

```bash
nvidia-smi
```

Select all currently available H200 GPU ids.

- [ ] **Step 4: Run complete 128-job sweep**

Run:

```bash
conda run -n vla-pilot python scripts/rdt_eds_eval_runner.py run-level \
  --level rollout_rbf_ablation \
  --episodes 3 \
  --gpus <comma-separated-free-gpu-ids> \
  --timeout-seconds 28800 \
  --cached-functions-dir /home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_1/vlm_agent \
  --offline-vlm \
  --resume
```

Expected: jobs complete or failed jobs have clear failure logs.

- [ ] **Step 5: Write final evidence report**

Run report writer or write a report manually if report writer cannot summarize edge cases. Include baseline references from:

- `2026-07-10-renoise-tmax-ablation-report.md`
- `2026-07-11-renoise-rt1to1-start08-supplement.md`

- [ ] **Step 6: Final verification**

Run:

```bash
git status --short
python scripts/rdt_eds_eval_runner.py write-report --level rollout_rbf_ablation --verdict inconclusive --evidence docs/03_evidence/eds_init_pg_diverse_sampling/YYYY-MM-DD-rollout-rbf-level3-parameter-sweep.md
```

Expected: report exists; status shows intended files only.

---

## Self-Review

This plan covers config/parser, rollout algorithm, metrics, trace, visualization, runner, tests, full experiment execution, and final report. It intentionally excludes parent diversity resampling, adaptive schedules, LIBERO-PRO full OOD evaluation, and non-EEF diversity metrics, matching the approved design.
