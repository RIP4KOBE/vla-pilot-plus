# P2 Adaptive EDS+RBF OOD Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 `p2_stage_on` baseline 和 VLS 路径的前提下，实现 adaptive ESS、adaptive rollout RBF、diversity-aware resampling、跨 chunk population memory、自适应搜索与执行 horizon，并完成同一 10 个 LIBERO-PRO `libero_object_swap` tasks 的单因素和集成 OOD 评测。

**Architecture:** 保留 `_eds_guided_denoise_loop()` 作为唯一 EDS 主控制流，把 parent weighting、parent plan、rollout diversity control、chunk population composition 和 search schedule 抽成组件级 strategy helper。所有新增 mode 使用 legacy/off 默认值，组合关闭时必须逐 tensor 回归到 `p2_stage_on`。正式实验先运行 11 个 Stage A 单因素 job，再根据预声明规则冻结最多 2 个 Stage B 集成 job；QD-ED 明确不在本计划范围内。

**Tech Stack:** Python 3、PyTorch、Hydra/OmegaConf、pytest、LIBERO-PRO、RDT、现有 EDS metrics/mechanism trace/qualitative 工具、线程式 GPU batch runner。

---

## Scope Lock

本计划只实现以下五个组件：

1. `parent_weighting_mode=adaptive_ess`；
2. `rollout_diversity_control_mode=adaptive_band`；
3. `parent_coverage_mode=eef_kcenter` 与 elite carryover；
4. `chunk_population_mode=warm_start_mix`；
5. `search_schedule_mode=adaptive` 与 `execution_horizon_mode=adaptive_prefix`。

本计划明确不实现：

- `qd_archive_mode`、MAP-Elites、QD archive 或 QD parent sampling；
- 新 reward、Gemini grounding、Stage Recognition prompt/state-machine 修改；
- VLS 路径修改；
- RDT checkpoint、scheduler inference step 数、128D action layout 修改；
- 自动超参数优化或正式矩阵外的结果驱动加跑。

## Baseline Contract

`p2_stage_on` 必须保持：

```yaml
main.use_vlm_stage_recognition: true
perception.gemini_grounding.enabled: false
main.eds_config:
  population_size: 16
  cem_iters: 10
  use_cem: false
  num_elites: 16
  temperature: 0.1
  renoise_t_max: 3
  renoise_t_min: 1
  initial_sampling_mode: rbf_diverse_denoise
  initial_diversity_scale: 20.0
  initial_diversity_start_ratio: 0.8
  truncated_rollout_mode: rbf_diverse
  rollout_diversity_scale: 20.0
  rollout_diversity_start_ratio: 0.6
  rollout_diversity_iters: all
  parent_weighting_mode: legacy_temperature
  parent_coverage_mode: none
  rollout_diversity_control_mode: fixed
  chunk_population_mode: fresh
  search_schedule_mode: legacy_linear
main.execution_horizon_mode: fixed
```

## Files And Responsibilities

- `core/rdt_policy_steer.py`: strategy config、adaptive ESS、parent plan、adaptive RBF decision、memory state、adaptive renoise/early stop、统一 EDS loop。
- `core/eds_eval_metrics.py`: component-level chunk/iteration metrics schema。
- `core/eds_mechanism_trace.py`: parent source、memory source、adaptive decision trace。
- `main.py`: stage/guidance reset hook、adaptive execution prefix、episode-level execution telemetry。
- `configs/config.yaml`: legacy-safe defaults。
- `utils/eds_mechanism_pretest_vis.py`: parent/memory/schedule qualitative artifacts。
- `scripts/rdt_eds_eval_runner.py`: storage preflight、Stage A/Stage B/pretest registries、resume/validity、manifest 和报告。
- `tests/test_rdt_steer.py`: core strategy 与 baseline regression。
- `tests/test_eds_eval_metrics.py`: JSON schema serialization。
- `tests/test_eds_mechanism_pretest_vis.py`: qualitative artifact tests。
- `tests/test_main_rdt_startup.py`: execution horizon 与 reset integration。
- `tests/test_eds_eval_runner.py`: 11/2 job matrix、storage、resume、manifest、validity、report。
- `docs/03_evidence/eds_init_pg_diverse_sampling/`: pretest、Stage A、Stage B 和最终报告。

## Storage Decision

2026-08-02 实测：

| 资源 | 状态 | 判断 |
|---|---:|---|
| home/root filesystem | 437 GiB 总量，56 GiB 可用，87% 已用 | 预计容量够，但不适合继续长期堆放 artifact |
| worktree `outputs` | 130 GiB | 已是 root 占用的主要来源 |
| 历史 Level-4 10-episode job | 257 jobs，均值 431.6 MiB，最大 449.2 MiB | 可用于本轮估算 |
| 本轮正式实验上限 | 13 jobs，约 5.48 GiB | 加 50% 余量约 8.22 GiB |
| `/mnt/data/shared2` | 14 TiB 总量，4.1 TiB 可用，可写 | 推荐作为真实 artifact 根目录 |
| 系统 RAM | 1.0 TiB，总 available 约 634 GiB | 足够 4 个并行 evaluation worker |
| swap | 8 GiB 已使用 | 运行时监控，但当前 available RAM 充足 |

真实输出目录固定为：

```text
/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/
  outputs/ood_eval/p2_adaptive_eds_rbf/
```

兼容软链接固定为：

```text
<worktree>/outputs/ood_eval/p2_adaptive_eds_rbf
  -> /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
```

---

### Task 1: Freeze Dirty-Worktree Boundary And Prepare Storage

**Files:**
- Modify: none
- Create at runtime: `/mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf/`
- Create at runtime: `outputs/ood_eval/p2_adaptive_eds_rbf` symlink

- [ ] **Step 1: Record the current dirty-worktree boundary**

Run:

```bash
git status --short
git diff --stat
```

Expected: existing RBF/EDS changes are present. Do not reset, checkout, clean, or revert them. Before each later commit, stage only the files named by that task and inspect `git diff --cached --stat`.

- [ ] **Step 2: Recheck storage and permissions**

Run:

```bash
df -hT /home/hynx /mnt/data/shared2
df -ih /home/hynx /mnt/data/shared2
test -w /mnt/data/shared2
```

Expected: shared2 is writable and has at least 20 GiB free; inode usage is below 90%.

- [ ] **Step 3: Create the real artifact directory**

Run:

```bash
mkdir -p /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf
```

Expected: directory exists on `/dev/sdc1`, not `/dev/sda3`.

- [ ] **Step 4: Create the compatibility symlink without touching old outputs**

Run:

```bash
test ! -e outputs/ood_eval/p2_adaptive_eds_rbf
ln -s /mnt/data/shared2/hynx/VLA-Pilot++/eds-init-pg-diverse-sampling/outputs/ood_eval/p2_adaptive_eds_rbf outputs/ood_eval/p2_adaptive_eds_rbf
readlink -f outputs/ood_eval/p2_adaptive_eds_rbf
```

Expected: the resolved path is exactly the shared2 path above. If the worktree path already exists, inspect it and resume it; never delete or replace it blindly.

- [ ] **Step 5: Write a storage preflight record**

Save command output and the resolved link target to:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-storage-preflight.md
```

Include root/shared2 capacity, inode usage, RAM, symlink target and timestamp.

---

### Task 2: Add Legacy-Safe Strategy Config And Typed Plans

**Files:**
- Modify: `core/rdt_policy_steer.py:50-82`
- Modify: `core/rdt_policy_steer.py:3448-3545`
- Modify: `configs/config.yaml:57-79`
- Modify: `core/eds_eval_metrics.py:11-97`
- Test: `tests/test_rdt_steer.py`
- Test: `tests/test_eds_eval_metrics.py`

- [ ] **Step 1: Add failing default and validation tests**

Add tests with these assertions:

```python
def test_eds_new_strategy_defaults_preserve_p2_legacy(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})
    assert cfg.parent_weighting_mode == "legacy_temperature"
    assert cfg.parent_coverage_mode == "none"
    assert cfg.rollout_diversity_control_mode == "fixed"
    assert cfg.chunk_population_mode == "fresh"
    assert cfg.search_schedule_mode == "legacy_linear"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("parent_weighting_mode", "qd"),
        ("parent_coverage_mode", "fps_action"),
        ("rollout_diversity_control_mode", "auto"),
        ("chunk_population_mode", "archive"),
        ("search_schedule_mode", "oracle"),
    ],
)
def test_eds_rejects_unknown_strategy_modes(stub_steer, field, value):
    with pytest.raises(ValueError, match=field):
        stub_steer._resolve_eds_config_with_reference_defaults({field: value})
```

- [ ] **Step 2: Verify tests fail before implementation**

Run:

```bash
pytest tests/test_rdt_steer.py -k 'new_strategy_defaults or unknown_strategy_modes' -q
```

Expected: FAIL because the new fields do not exist.

- [ ] **Step 3: Add `_EDSConfig` fields with legacy defaults**

Add exactly these fields:

```python
parent_weighting_mode: str = "legacy_temperature"
selection_ess_target_ratio: float = 0.6
selection_beta_max: float = 100.0
selection_bisection_steps: int = 24
parent_coverage_mode: str = "none"
parent_anchor_count: int = 0
parent_anchor_reward_quantile: float = 0.5
elite_carryover_count: int = 0
rollout_diversity_control_mode: str = "fixed"
rollout_diversity_target_ratio: float = 1.0
rollout_diversity_band_ratio: float = 0.2
rollout_diversity_scale_min: float = 0.0
rollout_diversity_scale_max: float = 20.0
rollout_diversity_decay_floor: float = 0.25
chunk_population_mode: str = "fresh"
chunk_memory_fraction: float = 0.0
chunk_memory_renoise_steps: int = 2
chunk_memory_reward_guard_quantile: float = 0.25
search_schedule_mode: str = "legacy_linear"
adaptive_min_cem_iters: int = 4
adaptive_early_stop_patience: int = 2
adaptive_reward_improvement_eps: float = 1e-3
```

Do not add any QD field.

- [ ] **Step 4: Add typed internal records**

Place near `_EDSConfig`:

```python
@dataclass(frozen=True)
class EDSParentPlan:
    elite_indices: Tensor
    offspring_parent_indices: Tensor
    offspring_sources: tuple[str, ...]
    info: dict


@dataclass(frozen=True)
class EDSRolloutDiversityDecision:
    scale: float
    enabled: bool
    reason: str
    reference: float
    low: float
    high: float
    current: float
    reward_confidence: float


@dataclass
class EDSChunkMemory:
    population: Tensor
    costs: Tensor
    stage: int
    global_step: int
```

- [ ] **Step 5: Parse and validate all fields**

Validation rules:

```text
selection_ess_target_ratio in (0, 1]
selection_beta_max finite and > 0
selection_bisection_steps > 0
parent_anchor_count >= 0
parent_anchor_reward_quantile in [0, 1]
elite_carryover_count >= 0
elite + anchors <= population_size
rollout target/band finite and >= 0
scale_min <= scale_max and both finite/nonnegative
decay_floor in [0, 1]
chunk_memory_fraction in [0, 1)
chunk_memory_renoise_steps > 0
chunk_memory_reward_guard_quantile in [0, 1]
adaptive_min_cem_iters in [1, cem_iters]
adaptive_early_stop_patience > 0
adaptive_reward_improvement_eps finite and >= 0
```

- [ ] **Step 6: Add defaults to Hydra config**

Add the same fields under `main.eds_config` with legacy/off values. Keep existing initial and rollout RBF defaults unchanged.

- [ ] **Step 7: Add metrics schema before algorithm wiring**

Extend `EDSIterMetrics` with optional/defaulted fields:

```python
selection_beta: float | None = None
selection_ess: float | None = None
selection_ess_ratio: float | None = None
selection_entropy_normalized: float | None = None
selection_max_probability: float | None = None
selection_degenerate_reward: bool = False
elite_count: int = 0
anchor_count: int = 0
anchor_min_pairwise_eef_distance: float | None = None
resolved_rollout_diversity_scale: float | None = None
adaptive_rbf_trigger_reason: str | None = None
resolved_renoise_reason: str | None = None
```

Extend `EDSChunkMetrics` with component modes, memory, early-stop and execution fields from the design. All new fields must have JSON-safe defaults.

- [ ] **Step 8: Run config and serialization tests**

Run:

```bash
pytest tests/test_rdt_steer.py -k 'config' -q
pytest tests/test_eds_eval_metrics.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit the config/schema unit**

```bash
git add core/rdt_policy_steer.py core/eds_eval_metrics.py configs/config.yaml tests/test_rdt_steer.py tests/test_eds_eval_metrics.py
git diff --cached --check
git commit -m "feat(eds): add adaptive strategy configuration"
```

Before committing, confirm no unrelated pre-existing hunk is accidentally staged.

---

### Task 3: Implement Adaptive ESS Parent Weighting

**Files:**
- Modify: `core/rdt_policy_steer.py:1672-1693`
- Modify: `core/rdt_policy_steer.py:2913-2940`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing numerical tests**

```python
def test_adaptive_ess_probabilities_hit_target(stub_steer):
    costs = torch.tensor([-4.0, -2.0, -1.0, 0.0])
    probs, info = stub_steer._eds_adaptive_ess_probabilities(
        costs, target_ratio=0.5, beta_max=100.0, bisection_steps=24
    )
    ess = 1.0 / probs.square().sum()
    assert abs(float(ess / costs.numel()) - 0.5) <= 0.03
    assert torch.argmax(probs).item() == torch.argmin(costs).item()
    assert info["selection_degenerate_reward"] is False


def test_adaptive_ess_equal_rewards_return_uniform(stub_steer):
    probs, info = stub_steer._eds_adaptive_ess_probabilities(
        torch.zeros(16), target_ratio=0.5, beta_max=100.0, bisection_steps=24
    )
    assert torch.allclose(probs, torch.full((16,), 1 / 16))
    assert info["selection_degenerate_reward"] is True
```

- [ ] **Step 2: Run tests and confirm failure**

```bash
pytest tests/test_rdt_steer.py -k 'adaptive_ess' -q
```

Expected: FAIL because helper is missing.

- [ ] **Step 3: Implement robust normalization**

Add `_eds_robust_normalize_rewards()`:

```text
median/MAD -> 1.4826 * MAD
if scale <= 1e-8, use population std
if std <= 1e-8, return zeros and degenerate=True
otherwise return finite normalized rewards
```

- [ ] **Step 4: Implement ESS bisection**

Use float64 logits for stability. Start `beta_low=0`, `beta_high=selection_beta_max`; after 24 iterations move the bound according to whether current ESS/N is above or below target. Return normalized float32 probabilities on the costs device plus beta/ESS/entropy/max-probability telemetry.

- [ ] **Step 5: Add strategy dispatch without changing legacy helper**

```python
def _eds_compute_parent_weights(self, costs: Tensor, cfg: _EDSConfig):
    if cfg.parent_weighting_mode == "legacy_temperature":
        probs = self._eds_sampling_probabilities_from_cost(costs, cfg.temperature)
        return probs, legacy_info
    return self._eds_adaptive_ess_probabilities(
        costs,
        target_ratio=cfg.selection_ess_target_ratio,
        beta_max=cfg.selection_beta_max,
        bisection_steps=cfg.selection_bisection_steps,
    )
```

- [ ] **Step 6: Add seeded legacy regression**

With identical costs and `torch.manual_seed`, assert `legacy_temperature` produces exactly the same probabilities and `torch.multinomial` parent indices as the old helper.

- [ ] **Step 7: Run tests**

```bash
pytest tests/test_rdt_steer.py -k 'sampling_probabilities or adaptive_ess or parent_weight' -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git diff --cached --check
git commit -m "feat(eds): add adaptive ESS parent weighting"
```

---

### Task 4: Implement Diversity-Aware Parent Plan And Elite Bypass

**Files:**
- Modify: `core/rdt_policy_steer.py:2687-2691`
- Modify: `core/rdt_policy_steer.py:2913-3029`
- Modify: `core/eds_mechanism_trace.py:13-64`
- Test: `tests/test_rdt_steer.py`
- Test: `tests/test_eds_mechanism_pretest_vis.py`

- [ ] **Step 1: Add failing k-center tests**

Cover deterministic best-first selection, reward quantile guard, duplicate removal and lower-index tie break:

```python
def test_eef_kcenter_starts_from_best_and_respects_reward_guard(stub_steer, monkeypatch):
    rewards = torch.tensor([10.0, 9.0, 8.0, -100.0])
    features = torch.tensor([[0.0], [1.0], [2.0], [100.0]])
    monkeypatch.setattr(stub_steer, "_eds_population_to_reward_trajectories", lambda _: features)
    indices, info = stub_steer._eds_select_eef_kcenter(
        torch.zeros(4, 64, 128), rewards, count=2, reward_quantile=0.5
    )
    assert indices.tolist()[0] == 0
    assert 3 not in indices.tolist()
    assert len(set(indices.tolist())) == 2
```

- [ ] **Step 2: Add failing parent-plan shape tests**

For `N=16, elite=2, anchors=4`, assert:

```text
elite_indices shape == (2,)
offspring_parent_indices shape == (14,)
first four offspring sources are anchor
remaining ten sources are weighted
all indices are in [0, 15]
```

- [ ] **Step 3: Implement `_eds_select_eef_kcenter()`**

Flatten `_eds_population_to_reward_trajectories(population)` to `(N, -1)`, compute distances with `torch.cdist`, select best reward first, then maximize minimum distance. Restrict candidates to rewards at or above `torch.quantile(rewards, q)`; tie break by reward descending then original index ascending.

- [ ] **Step 4: Implement `_eds_select_parent_plan()`**

Behavior:

```text
legacy coverage + zero elites: return N weighted parent indices, preserving old sampling
elite count E: top-E lowest-cost indices bypass perturbation
anchor count A: exclude elite indices, then select A unique reward-eligible k-center parent indices
offspring slots: A anchors followed by N-E-A weighted samples
if the non-elite eligible pool has fewer than A candidates, warn, record the shortfall and return those slots to weighted sampling
```

- [ ] **Step 5: Refactor loop to mutate offspring only**

Replace the direct `population = population[parent_indices]` block with:

```python
plan = self._eds_select_parent_plan(population, population_scores, cfg)
elite_population = population.index_select(0, plan.elite_indices)
offspring = population.index_select(0, plan.offspring_parent_indices)
offspring = self._eds_renoise_reference(offspring, n_trunc_steps)
offspring, _, offspring_info = self._eds_rollout_reference(..., noisy_action=offspring)
population = torch.cat([elite_population, offspring], dim=0)
population = self._apply_action_mask(population, cond)
population_scores, population_info = self._eds_score_population_as_cost(...)
```

Always score the concatenated population so elite and offspring rewards use one current scoring path. Validate final shape `(N, 64, 128)`.

- [ ] **Step 6: Preserve scheduler semantics**

Reset scheduler particle history only for the offspring rollout. Add a regression where `elite_carryover_count=0` and `parent_coverage_mode=none` produces the same population and selected index as the pre-refactor loop under a fixed seed.

- [ ] **Step 7: Extend trace source metadata**

Add `particle_sources: list[str] | None` to `EDSParticleStage` and CSV field `particle_source`. Record `elite`, `anchor_offspring`, or `weighted_offspring` after each rollout. Keep old trace files readable when the field is absent.

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_rdt_steer.py -k 'kcenter or parent_plan or elite or legacy_parent' -q
pytest tests/test_eds_mechanism_pretest_vis.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/rdt_policy_steer.py core/eds_mechanism_trace.py tests/test_rdt_steer.py tests/test_eds_mechanism_pretest_vis.py
git diff --cached --check
git commit -m "feat(eds): preserve diverse parents and elites"
```

---

### Task 5: Implement Adaptive Rollout RBF Controller

**Files:**
- Modify: `core/rdt_policy_steer.py:2114-2400`
- Modify: `core/rdt_policy_steer.py:2493-2645`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing controller tests**

Test these deterministic cases:

```text
D_current < D_low and low reward confidence -> positive scale
D_current inside band -> scale 0, reason in_band
D_current > D_high -> scale 0, reason above_band
later iter scale <= earlier iter scale for same state
high confidence scale <= low confidence scale
nonfinite reference warns and returns fixed cfg.rollout_diversity_scale fallback
```

- [ ] **Step 2: Implement reward confidence**

Use detached rewards:

```text
scale = 1.4826 * MAD, fallback std
confidence = clamp((best - median) / max(3 * scale, eps), 0, 1)
degenerate rewards -> confidence 0
```

- [ ] **Step 3: Implement controller decision**

```python
deficit = clamp((low - current) / max(low, eps), 0.0, 1.0)
iter_decay = max(decay_floor, 1.0 - iter_idx / max(cem_iters - 1, 1))
scale = clip(scale_max * deficit * iter_decay * (1.0 - confidence), scale_min, scale_max)
```

Set `enabled = scale > 0`. Record reference, band, current, confidence and reason.

- [ ] **Step 4: Inject scale as an explicit rollout override**

Extend `_eds_rollout_reference()` and `_eds_rollout_rbf_diverse_reference()` with `diversity_scale_override: float | None`. Use the override only when control mode is adaptive; fixed mode must continue reading `cfg.rollout_diversity_scale` exactly as before.

- [ ] **Step 5: Implement warned fallback**

Controller calculation failure logs one warning containing iteration and reason, records `adaptive_rbf_fallback_used/reason`, and uses the configured fixed P2 rollout scale for that call. Diversity-gradient failure continues using the existing warned baseline-denoise fallback.

- [ ] **Step 6: Record per-iteration controller metrics**

Populate `diversity_reference/low/high/current`, requested/applied scale, trigger reason, active particle count, active-iteration ratio and band-hit ratio.

- [ ] **Step 7: Verify fixed P2 regression and adaptive behavior**

```bash
pytest tests/test_rdt_steer.py -k 'rollout_rbf or adaptive_rbf or rollout_diversity' -q
```

Expected: all existing fixed-RBF tests and new adaptive tests PASS.

- [ ] **Step 8: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git diff --cached --check
git commit -m "feat(eds): adapt rollout RBF to population diversity"
```

---

### Task 6: Implement Cross-Chunk Population Memory

**Files:**
- Modify: `core/rdt_policy_steer.py:716-746`
- Modify: `core/rdt_policy_steer.py:1116-1135`
- Modify: `core/rdt_policy_steer.py:2008-2102`
- Modify: `core/rdt_policy_steer.py:2775-3215`
- Modify: `main.py:680-730`
- Test: `tests/test_rdt_steer.py`
- Test: `tests/test_main_rdt_startup.py`

- [ ] **Step 1: Add failing shift/fill tests**

For an action tensor with step IDs and `executed_steps=4`, assert the first 60 rows come from memory rows 4:64 and the final 4 rows come from the paired fresh candidate, not zeros.

- [ ] **Step 2: Extract score-free truncated denoise helper**

Extract the denoise body used by `_eds_rollout_baseline_reference()` into:

```python
def _eds_denoise_noisy_population(
    self, *, cond: dict, action_mask: Tensor, noisy_action: Tensor, n_trunc_steps: int
) -> Tensor:
    ...
```

Baseline rollout calls this helper and then scores. Memory adaptation calls it without introducing a second rollout algorithm.

- [ ] **Step 3: Add memory state and reset API**

Initialize `self._eds_chunk_memory = None`. Add:

```python
def reset_eds_chunk_memory(self, reason: str, *, warn: bool = False) -> None:
    ...
```

`reset()` clears it silently as `episode_reset`; `reset_stage()` clears it as `stage_change`; abnormal invalidation logs a warning.

- [ ] **Step 4: Implement memory composition**

After `_eds_initial_population()` and action mask:

1. resolve `executed_steps = global_step - memory.global_step`;
2. select previous best and diversity-preserving candidates from stored final population;
3. shift and fresh-tail fill;
4. apply mask;
5. renoise with `chunk_memory_renoise_steps` and denoise under current `cond`;
6. score adapted memory and fresh population;
7. accept memory whose reward is at least the configured fresh reward quantile;
8. fill rejected slots with fresh candidates;
9. return exactly `(N, 64, 128)` and structured telemetry.

- [ ] **Step 5: Store final memory after selection**

Save detached final population and costs plus `current_stage/global_step`. Store tensors on CPU; move them back to the current device only when composing the next chunk.

- [ ] **Step 6: Wire stage/guidance invalidation**

Keep existing `policy.reset_stage()` on stage changes. When guidance toggles without a stage change, call `reset_eds_chunk_memory("guidance_change")` if the policy exposes it. Never call this hook on VLS-only policies that do not implement it.

- [ ] **Step 7: Add memory tests**

Cover:

```text
fresh mode never reads or creates memory
25% and 50% resolve to 4 and 8 candidates for N=16
shape/mask/nonfinite invalid memory warns and falls back to all fresh
episode/stage/guidance reset clears memory
initial cache stores only fresh initial population
memory state never survives reset()
```

- [ ] **Step 8: Run tests**

```bash
pytest tests/test_rdt_steer.py -k 'chunk_memory or warm_start or initial_cache' -q
pytest tests/test_main_rdt_startup.py -k 'stage or guidance or memory' -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/rdt_policy_steer.py main.py tests/test_rdt_steer.py tests/test_main_rdt_startup.py
git diff --cached --check
git commit -m "feat(eds): carry population modes across chunks"
```

---

### Task 7: Implement Adaptive Renoise And EDS Early Stop

**Files:**
- Modify: `core/rdt_policy_steer.py:2907-2914`
- Modify: `core/rdt_policy_steer.py:3101-3127`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing schedule tests**

Test pure helper decisions:

```text
legacy_linear equals np.linspace(max, min, cem_iters).astype(int)
first adaptive iteration uses renoise_t_max
low diversity plus no improvement resolves t=3
stable improving lineage inside band resolves t=1
uncertain state resolves t=2
resolved value is always clipped to [renoise_t_min, renoise_t_max]
```

- [ ] **Step 2: Implement `_eds_resolve_renoise_steps()`**

The helper receives only online history: previous/current best reward, current diversity band state, whether the current best descends from the previous best, and iteration index. It must not receive simulator success.

- [ ] **Step 3: Implement early-stop state**

Track plateau count, previous best index/lineage and reward improvement. Stop only when all are true:

```text
executed iterations >= adaptive_min_cem_iters
abs(best reward improvement) <= adaptive_reward_improvement_eps
plateau count >= adaptive_early_stop_patience
best lineage is stable
diversity is inside target band
```

- [ ] **Step 4: Preserve legacy loop count**

When `search_schedule_mode=legacy_linear`, always execute exactly `cem_iters`, preserve the existing truncation schedule and set `early_stop_used=false`.

- [ ] **Step 5: Record metrics**

Store per-iteration `resolved_renoise_steps/reason`, chunk `eds_iters_executed`, `early_stop_used/reason`, and reward plateau count.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_rdt_steer.py -k 'adaptive_schedule or early_stop or trunc_step_schedule' -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git diff --cached --check
git commit -m "feat(eds): adapt renoise schedule and iteration budget"
```

---

### Task 8: Implement Adaptive Execution Prefix In The Environment Loop

**Files:**
- Modify: `configs/config.yaml:26-40`
- Modify: `main.py:878-940`
- Modify: `main.py:1050-1113`
- Modify: `main.py:1225-1230`
- Test: `tests/test_main_rdt_startup.py`

- [ ] **Step 1: Add pure helper tests**

Add `_resolve_execution_horizon()` tests:

```text
fixed mode -> policy horizon 8
guidance OFF -> 8
stage changed -> at most 4
target distance <= 0.04 or gripper edge in prefix -> 2
target distance <= 0.08 -> 4
far target -> 8
result always in {2, 4, 8} and <= policy horizon
```

- [ ] **Step 2: Add main config defaults**

```yaml
execution_horizon_mode: fixed
execution_horizon_far: 8
execution_horizon_near: 4
execution_horizon_contact: 2
execution_near_distance: 0.08
execution_contact_distance: 0.04
```

- [ ] **Step 3: Resolve the prefix after each new chunk**

After `select_action()` returns, read `policy.get_last_eds_metrics()` and the decoded gripper transition. Resolve a per-chunk `resolved_action_horizon`; do not change `policy._action_chunk_horizon` or the 8-step scoring slice.

- [ ] **Step 4: Replan at the resolved prefix**

Replace:

```python
if action_executed == action_horizon:
    action_executed = 0
```

with comparison against `resolved_action_horizon`. The next loop then sets `generate_new_chunk=True`, while RDT output shape remains unchanged.

- [ ] **Step 5: Attach execution telemetry before JSONL write**

Add `execution_horizon_resolved`, reason, stage-change flag and replan count to the EDS metrics record. Fixed mode must continue reporting 8 without behavior change.

- [ ] **Step 6: Run main tests**

```bash
pytest tests/test_main_rdt_startup.py -k 'execution_horizon or action_horizon or stage' -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add main.py configs/config.yaml tests/test_main_rdt_startup.py
git diff --cached --check
git commit -m "feat(eds): adapt closed-loop execution horizon"
```

---

### Task 9: Complete Metrics, Trace And Qualitative Evidence

**Files:**
- Modify: `core/eds_eval_metrics.py`
- Modify: `core/eds_mechanism_trace.py`
- Modify: `utils/eds_mechanism_pretest_vis.py`
- Modify: `main.py`
- Test: `tests/test_eds_eval_metrics.py`
- Test: `tests/test_eds_mechanism_pretest_vis.py`

- [ ] **Step 1: Add a complete metrics round-trip test**

Construct one `EDSChunkMetrics` containing every new field, call `to_jsonable()`, write with `append_jsonl()`, read it, and assert values/types are preserved without tensors or NaN.

- [ ] **Step 2: Extend trace metadata**

Record:

```text
parent_weighting_mode and ESS decision
elite/anchor/weighted source per particle
adaptive RBF decision per iteration
memory availability/acceptance/reset/source
resolved renoise and early-stop state
execution prefix and reason
```

- [ ] **Step 3: Add qualitative artifacts**

Under each selected qualitative chunk, generate:

```text
selection/parent_source_trajectories_3d.png
selection/parent_rank_and_probability.csv
selection/elite_anchor_survival.json
memory/fresh_vs_memory_trajectories_3d.png
memory/memory_acceptance.json
schedule/adaptive_decisions.json
schedule/reward_diversity_schedule.png
```

Use existing plotting helpers and fixed axes; do not create a second visualization framework.

- [ ] **Step 4: Add artifact tests**

Synthetic traces must create nonempty files and JSON values matching the trace. Missing optional modes should omit their directory rather than create misleading empty plots.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_eds_eval_metrics.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/eds_eval_metrics.py core/eds_mechanism_trace.py utils/eds_mechanism_pretest_vis.py main.py tests/test_eds_eval_metrics.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py
git diff --cached --check
git commit -m "feat(eds): trace adaptive steering mechanisms"
```

---

### Task 10: Extend Runner, Storage Gate And Experiment Registries

**Files:**
- Modify: `scripts/rdt_eds_eval_runner.py`
- Test: `tests/test_eds_eval_runner.py`

- [ ] **Step 1: Add failing storage-preflight tests**

Test a helper that rejects regular files, dangling links, links resolving under home/root, unwritable targets, and targets with less than 20 GiB free. Accept only the expected shared2 target.

- [ ] **Step 2: Implement `_validate_p2_output_storage()`**

Before `init` or `run-level` for the new levels, require:

```text
worktree output path is a symlink
resolved path starts with /mnt/data/shared2/hynx/VLA-Pilot++/
target is writable
free bytes >= 20 GiB
```

On failure, raise before submitting any GPU job. Do not auto-delete or rewrite an existing path.

- [ ] **Step 3: Add Stage A method registry with exactly 11 methods**

Registry labels:

```text
p2_legacy_stage_on_rerun
p2_sel_ess05
p2_sel_ess07
p2_adaptrbf_t08_s10
p2_adaptrbf_t10_s20
p2_divres_k2_e1
p2_divres_k4_e2
p2_memory25
p2_memory50
p2_schedule_balanced
p2_schedule_contact
```

Every method must emit every component mode explicitly. The baseline emits only legacy/off values; each single-factor profile changes only its named component.

- [ ] **Step 4: Add pretest registry with exactly 6 representative profiles**

Use baseline, ESS 0.5, adaptive RBF target 1.0/max 20, k-center 4/elite 2, memory 25%, and contact schedule. Apply task filter `[0, 8]`, one episode per task, for 12 pretest episodes total.

- [ ] **Step 5: Add Stage B manifest loader**

`build_jobs("p2_adaptive_eds_rbf_stage_b", ...)` must require an immutable JSON manifest with zero to two profiles. Validate:

```text
label is p2_integrated_full or p2_integrated_minimal
all overrides are known component fields
source Stage A jobs are valid and eligible
manifest contains git revision, Stage A report hash and creation timestamp
manifest hash is copied into every job config fingerprint
```

- [ ] **Step 6: Build exact Hydra commands**

Every job must set:

```text
backend.libero.suite_name=libero_object_swap
backend.libero.strict_perturbations=true
backend.libero.max_episode_steps=720
main.episode_num=10
main.use_vlm_stage_recognition=true
perception.gemini_grounding.enabled=false
seed=0
all P2 fixed RBF baseline fields
all new component modes and parameters
main.eds_eval.save_qualitative=true
main.eds_mechanism_pretest.output_mode=qualitative_chunk
```

Credentials remain runtime environment variables and must not appear in command strings, Hydra files, manifests or reports.

- [ ] **Step 7: Extend strict validity**

Complete job requires parseable `results.txt`, all 10 episode records, 10 ffprobe-readable videos, nonempty metrics and qualitative evidence, strict suite overrides, config fingerprint match, successful Stage Recognition query trace, no normal-LIBERO fallback and no serialized credential.

- [ ] **Step 8: Add runner tests**

```python
def test_p2_stage_a_matrix_has_11_controlled_jobs(): ...
def test_p2_pretest_has_6_profiles_and_tasks_0_8(): ...
def test_p2_stage_b_rejects_more_than_two_profiles(tmp_path): ...
def test_p2_stage_b_manifest_is_fingerprint_bound(tmp_path): ...
def test_p2_storage_rejects_home_target(tmp_path): ...
def test_p2_resume_skips_only_strictly_valid_jobs(tmp_path): ...
```

- [ ] **Step 9: Run runner tests**

```bash
pytest tests/test_eds_eval_runner.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add scripts/rdt_eds_eval_runner.py tests/test_eds_eval_runner.py
git diff --cached --check
git commit -m "feat(eval): add P2 adaptive OOD experiment runner"
```

---

### Task 11: Run Full Regression And Static Gates

**Files:**
- Modify only if a test exposes a scoped defect

- [ ] **Step 1: Run focused suites**

```bash
pytest tests/test_rdt_steer.py tests/test_eds_eval_metrics.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py tests/test_eds_eval_runner.py -q
```

Expected: PASS.

- [ ] **Step 2: Run adjacent RDT/LIBERO tests**

```bash
pytest tests/test_rdt_libero_obs_processor.py tests/test_stage_recognition_trace.py tests/test_stage_recognition_eval_runner.py -q
```

Expected: PASS.

- [ ] **Step 3: Run baseline determinism test twice**

Run the legacy tensor regression twice in separate pytest invocations. Expected: identical parent indices, population tensor, scores and selected index.

- [ ] **Step 4: Run repository checks**

```bash
git diff --check
python -m py_compile core/rdt_policy_steer.py core/eds_eval_metrics.py core/eds_mechanism_trace.py main.py scripts/rdt_eds_eval_runner.py
```

Expected: no output from `git diff --check`; compilation succeeds.

- [ ] **Step 5: Record test evidence**

Write commands, timestamps, revisions and pass counts to:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-test-report.md
```

---

### Task 12: Run Mechanism Pretests On Free GPUs 2-5

**Files:**
- Create: shared2 pretest outputs through the worktree symlink
- Create: `docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-pretest-report.md`

- [ ] **Step 1: Check GPU availability**

```bash
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader
```

Select only currently idle GPUs from `2,3,4,5`; do not use 0,1,6,7 without explicit approval.

- [ ] **Step 2: Run strict LIBERO-PRO preflight and API health check**

The API key must be supplied through the environment without echoing it. Expected: strict perturbation files load, suite resolves to `libero_object_swap`, and Stage Recognition health check succeeds.

- [ ] **Step 3: Run all 6 representative profiles on Tasks 0 and 8**

Use the resume-capable pretest level. Do not drop a profile based on episode success.

- [ ] **Step 4: Apply mechanism gates**

Verify:

```text
adaptive ESS median target error <= 0.1
adaptive RBF uses at least two distinct scales
k-center/elite source counts match config
memory is used from the second eligible chunk and resets on stage change
adaptive schedule resolves at least two renoise or execution-horizon values
0 nonfinite, 0 mask violation, 0 silent fallback
all required qualitative artifacts are readable
```

- [ ] **Step 5: Write and commit pretest evidence**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-pretest-report.md
git commit -m "docs(eval): record P2 adaptive mechanism pretest"
```

---

### Task 13: Run Stage A 11-Job Controlled OOD Evaluation

**Files:**
- Create: `outputs/ood_eval/p2_adaptive_eds_rbf/stage_a/<method>/` through symlink
- Create: `docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md`

- [ ] **Step 1: Initialize and audit all 11 commands**

Confirm each command differs from baseline only in its declared component and includes `max_episode_steps=720`, Stage Recognition ON, Gemini grounding OFF and strict swap suite.

- [ ] **Step 2: Start all jobs with resume support**

Use all idle GPUs among `2,3,4,5`, maximum four workers. A failed job must not stop other jobs. Do not launch when shared2 free space is below 20 GiB.

- [ ] **Step 3: Resume until every job has a terminal state**

Every job must be `done`, `failed`, `invalid` or `blocked` with a machine-readable failure reason. Retry transient failures without changing config or seed.

- [ ] **Step 4: Validate every complete job**

Run the runner validity checker and ffprobe all videos. Any missing result, video, metric, qualitative artifact, strict override or successful stage query makes the job invalid.

- [ ] **Step 5: Write Stage A controlled-effect report**

For every single factor report SR, task-paired outcome, mechanism metric, latency, fallback and visible failure mode against `p2_legacy_stage_on_rerun`. Do not combine components yet.

- [ ] **Step 6: Commit Stage A evidence**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-stage-a-report.md
git commit -m "docs(eval): report P2 adaptive Stage A results"
```

---

### Task 14: Freeze Integration Manifest And Run Stage B

**Files:**
- Create: `docs/03_evidence/eds_init_pg_diverse_sampling/p2_adaptive_eds_rbf_integration_manifest.json`
- Create: `outputs/ood_eval/p2_adaptive_eds_rbf/stage_b/<method>/` through symlink

- [ ] **Step 1: Compute eligibility from Stage A only**

A component is eligible if its job is valid, has no silent fallback, and either has higher SR than baseline or has equal SR with improved primary mechanism metric, no new paired task regression and median latency <=1.5x baseline.

- [ ] **Step 2: Resolve at most two profiles deterministically**

```text
p2_integrated_full: best eligible setting from each compatible component
p2_integrated_minimal: only the two strongest compatible single factors
```

Tie break by paired success increment, primary mechanism metric, median latency, then lower config complexity. If a slot has no eligible composition, record `not_eligible` instead of filling it.

- [ ] **Step 3: Freeze manifest before Stage B**

Include exact Hydra overrides, source Stage A rows, selection reasons, git revision, Stage A report SHA256 and manifest SHA256. Do not edit after launching Stage B.

- [ ] **Step 4: Run Task 0/8 integration pretest**

Confirm every declared component actually activates and no baseline/strategy mode is accidentally shadowed.

- [ ] **Step 5: Run up to two 10-episode jobs**

Use idle GPUs among 2-5, resume support and the same strict validity rules. Do not change integration parameters based on intermediate success.

- [ ] **Step 6: Validate outputs and commit manifest**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/p2_adaptive_eds_rbf_integration_manifest.json
git commit -m "docs(eval): freeze P2 adaptive integration manifest"
```

---

### Task 15: Generate Final OOD Report And Completion Gate

**Files:**
- Create: `docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md`
- Create: aggregate CSV/JSON indexes under the same evidence directory

- [ ] **Step 1: Generate complete status tables**

Include Stage A 11 jobs and Stage B zero to two jobs with status, success count/rate, task outcomes, latency, videos, metrics, qualitative counts, strict verification, output/log paths and failure reason.

- [ ] **Step 2: Generate component analyses**

Report adaptive ESS, adaptive RBF, k-center/elite, memory and adaptive schedule separately before discussing integration. Include mechanism gates and visible failure classes.

- [ ] **Step 3: State the primary engineering gate**

The gate passes only if at least one valid new profile succeeds on `>=5/10` of the same fixed tasks. Historical P2 `3/10` and current rerun deltas are secondary evidence, not substitutes.

- [ ] **Step 4: Audit safety and experimental validity**

Confirm zero unreported fallback, zero nonfinite, zero action-mask violation, no ordinary-LIBERO fallback, all qpos execution errors remain in the denominator, and no credential appears in output text.

- [ ] **Step 5: Audit storage and processes**

```bash
df -hT /home/hynx /mnt/data/shared2
readlink -f outputs/ood_eval/p2_adaptive_eds_rbf
pgrep -af 'rdt_eds_eval_runner.py|main.py'
```

Expected: output resolves to shared2; no experiment process remains after completion.

- [ ] **Step 6: Run final verification**

```bash
pytest tests/test_rdt_steer.py tests/test_eds_eval_metrics.py tests/test_eds_mechanism_pretest_vis.py tests/test_main_rdt_startup.py tests/test_eds_eval_runner.py -q
git diff --check
test -s docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md
```

Expected: tests pass, no whitespace errors, report exists and is nonempty.

- [ ] **Step 7: Commit final evidence**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/2026-08-02-p2-adaptive-eds-rbf-object-swap-report.md docs/03_evidence/eds_init_pg_diverse_sampling/*.csv docs/03_evidence/eds_init_pg_diverse_sampling/*.json
git diff --cached --check
git commit -m "docs(eval): report P2 adaptive object-swap OOD results"
```

---

## Execution Order

严格按以下顺序执行：

```text
Task 1 storage/boundary
  -> Tasks 2-10 implementation with TDD
  -> Task 11 full regression
  -> Task 12 mechanism pretest
  -> Task 13 all Stage A jobs
  -> Task 14 immutable manifest and Stage B
  -> Task 15 final report/gate
```

不得跳过 Stage A 直接选择集成配置；不得在 Stage B 运行过程中修改 manifest；不得将 QD-ED 临时加入本轮矩阵。
