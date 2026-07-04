# EDS RBF-Diverse Initial Sampling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `initial_sampling_mode="rbf_diverse_denoise"` for EDS initial population generation, reusing VLS RBF diversity guidance while leaving EDS refinement unchanged.

**Architecture:** `RDTSteer._eds_initial_population()` becomes a small mode dispatcher: `iid` preserves current behavior, while `rbf_diverse_denoise` runs early VLS-style RBF diversity during initial denoising and then returns a standard masked `(population_size, 64, 128)` population. Metrics, cache metadata, and mechanism trace record the initial sampler behavior; `_eds_guided_denoise_loop()` continues to do the same score/resample/renoise/rollout/final selection.

**Tech Stack:** Python, PyTorch, dataclasses, Hydra/OmegaConf configs, pytest, existing RDT/LIBERO adapters, existing EDS metrics and mechanism trace utilities.

---

## Approved Spec

- Design doc: `docs/01_specs/eds-init-pg-diverse-sampling-design.md`
- Worktree: `/home/hynx/VLA-Pilot++/.worktrees/exp/eds-init-pg-diverse-sampling`
- Branch: `exp/eds-init-pg-diverse-sampling`

Key constraints from the approved design:

- Use only `initial_sampling_mode` as the mechanism switch.
- Do not add `initial_diversity_enabled`.
- Do not add `initial_diversity_allow_grad`.
- First implementation should be glue code around existing VLS diversity helpers.
- RBF distance space remains VLS-consistent 3D EEF trajectories.
- RBF fallback may return to iid baseline, but must log a warning and record metrics.
- Do not include FPS oversampling logic in this branch.
- EDS refinement remains gradient-free after initial population generation.

## File Map

Modify:

- `core/rdt_policy_steer.py`
  - Add `_EDSConfig` initial sampler fields.
  - Parse and validate new config fields in `_resolve_eds_config_with_reference_defaults()`.
  - Refactor `_eds_initial_population()` into mode dispatch.
  - Add iid/RBF helper methods, validation helper, cache metadata helper, and initial sampler stats helpers.
  - Add trace stages around initial diversity phase when mechanism pretest is enabled.
  - Keep `_vls_guided_denoise_loop()` behavior unchanged.

- `core/eds_eval_metrics.py`
  - Add optional initial sampler metrics to `EDSChunkMetrics`.

- `core/eds_mechanism_trace.py`
  - Add optional initial sampler metadata to `EDSMechanismTrace`.
  - Include the metadata in saved JSON and tensor payloads.

- `utils/eds_mechanism_pretest_vis.py`
  - Add filenames for new initial sampler trace stages.
  - Ensure final-selected comparison can use `initial_final` as the initial stage when present.

- `configs/config.yaml`
  - Add default `main.eds_config.initial_sampling_mode: iid` and related initial diversity defaults.

- `scripts/rdt_eds_mechanism_pretest_runner.py`
  - Add CLI/config options for `initial_sampling_mode`, diversity scale, and start ratio.
  - Include these overrides in generated commands.

- `scripts/rdt_eds_eval_runner.py`
  - Add RBF-diverse initial sampler jobs for smoke/full OOD evaluation.
  - Add report fields for initial sampler metrics, sweep id, GPU, and warnings.

- `tests/test_rdt_steer.py`
  - Add CPU-only tests for config parsing, iid parity, RBF path, fallback, action mask, metrics, cache metadata, and trace stages.

- `tests/test_eds_eval_metrics.py`
  - Add serialization coverage for new metrics fields.

- `tests/test_eds_mechanism_trace.py`
  - Add metadata serialization coverage.

- `tests/test_eds_mechanism_pretest_vis.py`
  - Add artifact filename coverage for new stages.

- `tests/test_eds_mechanism_pretest_runner.py`
  - Add command override coverage.

- `tests/test_eds_eval_runner.py`
  - Add job/command/report coverage for RBF-diverse initial sampler evaluation.

Create:

- `docs/03_evidence/eds_init_pg_diverse_sampling/README.md`
  - Evidence index and experiment report protocol.

Do not modify:

- VLS path semantics in `_vls_guided_denoise_loop()`.
- EPS-CoT / VLM reward logic.
- EDS resample, renoise, rollout, score, and final selection semantics.
- RDT action layout or LIBERO 7D decoding semantics.

---

## Task 1: Config Surface and Defaults

**Files:**

- Modify: `core/rdt_policy_steer.py`
- Modify: `configs/config.yaml`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing config default test**

Add to `tests/test_rdt_steer.py` near `test_eds_config_defaults_match_reference_signature`:

```python
def test_eds_config_defaults_keep_iid_initial_sampling(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})

    assert cfg.initial_sampling_mode == "iid"
    assert cfg.initial_diversity_scale == 1.0
    assert cfg.initial_diversity_start_ratio is None
    assert cfg.initial_diversity_fallback == "iid"
    assert cfg.initial_cache_metadata is True
```

- [ ] **Step 2: Add failing config validation tests**

Add:

```python
@pytest.mark.parametrize("mode", ["fps", "rbf", "", "iid+rbf"])
def test_eds_config_rejects_invalid_initial_sampling_mode(stub_steer, mode):
    with pytest.raises(ValueError, match="initial_sampling_mode"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_sampling_mode": mode}
        )


@pytest.mark.parametrize("scale", [float("nan"), float("inf"), -float("inf")])
def test_eds_config_rejects_nonfinite_initial_diversity_scale(stub_steer, scale):
    with pytest.raises(ValueError, match="initial_diversity_scale"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_scale": scale}
        )


@pytest.mark.parametrize("ratio", [-0.1, 1.1, float("nan"), float("inf")])
def test_eds_config_rejects_invalid_initial_diversity_start_ratio(stub_steer, ratio):
    with pytest.raises(ValueError, match="initial_diversity_start_ratio"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_start_ratio": ratio}
        )


def test_eds_config_rejects_non_iid_initial_diversity_fallback(stub_steer):
    with pytest.raises(ValueError, match="initial_diversity_fallback"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"initial_diversity_fallback": "raise"}
        )
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_config_defaults_keep_iid_initial_sampling \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_initial_sampling_mode \
       tests/test_rdt_steer.py::test_eds_config_rejects_nonfinite_initial_diversity_scale \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_initial_diversity_start_ratio \
       tests/test_rdt_steer.py::test_eds_config_rejects_non_iid_initial_diversity_fallback -q
```

Expected: FAIL because `_EDSConfig` does not yet define the new fields and parser does not validate them.

- [ ] **Step 4: Add `_EDSConfig` fields**

In `core/rdt_policy_steer.py`, extend `_EDSConfig`:

```python
    initial_sampling_mode: str = "iid"
    initial_diversity_scale: float = 1.0
    initial_diversity_start_ratio: Optional[float] = None
    initial_diversity_fallback: str = "iid"
    initial_cache_metadata: bool = True
```

- [ ] **Step 5: Parse new fields**

In `_resolve_eds_config_with_reference_defaults()`, add fields to `_EDSConfig(...)`:

```python
            initial_sampling_mode=str(cfg.get("initial_sampling_mode", "iid")),
            initial_diversity_scale=float(cfg.get("initial_diversity_scale", 1.0)),
            initial_diversity_start_ratio=(
                None
                if cfg.get("initial_diversity_start_ratio", None) is None
                else float(cfg.get("initial_diversity_start_ratio"))
            ),
            initial_diversity_fallback=str(cfg.get("initial_diversity_fallback", "iid")),
            initial_cache_metadata=_parse_eds_bool(
                cfg.get("initial_cache_metadata", True), "initial_cache_metadata"
            ),
```

Then add validation after existing reward mode validation:

```python
        if resolved.initial_sampling_mode not in {"iid", "rbf_diverse_denoise"}:
            raise ValueError(
                "EDS initial_sampling_mode must be one of iid, rbf_diverse_denoise"
            )
        if not math.isfinite(resolved.initial_diversity_scale):
            raise ValueError("EDS initial_diversity_scale must be finite")
        if resolved.initial_diversity_start_ratio is not None:
            ratio = float(resolved.initial_diversity_start_ratio)
            if not math.isfinite(ratio) or ratio < 0.0 or ratio > 1.0:
                raise ValueError(
                    "EDS initial_diversity_start_ratio must be None or a finite value in [0, 1]"
                )
        if resolved.initial_diversity_fallback != "iid":
            raise ValueError("EDS initial_diversity_fallback MVP only supports iid")
```

- [ ] **Step 6: Add Hydra defaults**

In `configs/config.yaml`, under `main.eds_config`, add:

```yaml
    initial_sampling_mode: iid
    initial_diversity_scale: 1.0
    initial_diversity_start_ratio: null
    initial_diversity_fallback: iid
    initial_cache_metadata: true
```

- [ ] **Step 7: Run config tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_config_defaults_match_reference_signature \
       tests/test_rdt_steer.py::test_eds_config_defaults_keep_iid_initial_sampling \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_initial_sampling_mode \
       tests/test_rdt_steer.py::test_eds_config_rejects_nonfinite_initial_diversity_scale \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_initial_diversity_start_ratio \
       tests/test_rdt_steer.py::test_eds_config_rejects_non_iid_initial_diversity_fallback -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add core/rdt_policy_steer.py configs/config.yaml tests/test_rdt_steer.py
git commit -m "feat: add EDS initial sampling config"
```

---

## Task 2: IID Helper Refactor With Cache Metadata

**Files:**

- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing iid parity test**

Add to `tests/test_rdt_steer.py` near `test_eds_initial_population_masks_cached_population`:

```python
def test_eds_initial_population_iid_mode_preserves_shape_and_mask(stub_steer):
    from core.rdt_policy_steer import _EDSConfig

    x_t = torch.ones(3, 64, 128)
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    cond = {"action_mask": action_mask}

    population = stub_steer._eds_initial_population(
        x_t=x_t,
        cond=cond,
        cfg=_EDSConfig(population_size=3, initial_sampling_mode="iid"),
    )

    assert tuple(population.shape) == (3, 64, 128)
    assert torch.count_nonzero(population[:, :, 0]) == 0
    assert torch.isfinite(population).all()
```

- [ ] **Step 2: Add failing cache metadata mismatch tests**

Add:

```python
def test_eds_initial_population_rejects_cache_strategy_mismatch(stub_steer, tmp_path):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "eds_initial.pt"
    torch.save(
        {
            "initial_population": torch.zeros(2, 64, 128),
            "metadata": {"initial_sampling_mode": "iid"},
        },
        cache_path,
    )
    action_mask = torch.ones(1, 1, 128)

    with pytest.raises(ValueError, match="initial_population_cache.*initial_sampling_mode"):
        stub_steer._eds_initial_population(
            x_t=torch.zeros(2, 64, 128),
            cond={"action_mask": action_mask},
            cfg=_EDSConfig(
                population_size=2,
                use_initial_cache=True,
                initial_population_cache=str(cache_path),
                initial_sampling_mode="rbf_diverse_denoise",
            ),
        )


def test_eds_initial_population_warns_for_legacy_cache_without_metadata(
    stub_steer, tmp_path, caplog
):
    from core.rdt_policy_steer import _EDSConfig

    cache_path = tmp_path / "legacy_eds_initial.pt"
    torch.save({"initial_population": torch.zeros(2, 64, 128)}, cache_path)
    action_mask = torch.ones(1, 1, 128)

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(2, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=2,
            use_initial_cache=True,
            initial_population_cache=str(cache_path),
            initial_sampling_mode="iid",
        ),
    )

    assert tuple(population.shape) == (2, 64, 128)
    assert "metadata" in caplog.text.lower()
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_initial_population_iid_mode_preserves_shape_and_mask \
       tests/test_rdt_steer.py::test_eds_initial_population_rejects_cache_strategy_mismatch \
       tests/test_rdt_steer.py::test_eds_initial_population_warns_for_legacy_cache_without_metadata -q
```

Expected: first test may pass with current code, cache metadata tests FAIL because metadata is ignored.

- [ ] **Step 4: Add initial sampler info helpers**

In `core/rdt_policy_steer.py`, add methods near `_eds_initial_population()`:

```python
    def _eds_empty_initial_sampler_info(self, cfg: _EDSConfig) -> dict:
        return {
            "initial_sampling_mode": cfg.initial_sampling_mode,
            "initial_diversity_scale": float(cfg.initial_diversity_scale),
            "initial_diversity_start_ratio": cfg.initial_diversity_start_ratio,
            "initial_diversity_steps": 0,
            "initial_diversity_grad_norm_mean": None,
            "initial_diversity_grad_norm_max": None,
            "initial_diversity_grad_failure_count": 0,
            "initial_diversity_fallback_used": False,
            "initial_diversity_fallback_reason": None,
            "initial_sampler_latency_s": None,
        }

    def _eds_initial_cache_metadata(self, cfg: _EDSConfig, info: dict) -> dict:
        return {
            "initial_sampling_mode": cfg.initial_sampling_mode,
            "initial_diversity_scale": float(cfg.initial_diversity_scale),
            "initial_diversity_start_ratio": cfg.initial_diversity_start_ratio,
            "initial_diversity_fallback": cfg.initial_diversity_fallback,
            "initial_diversity_steps": int(info.get("initial_diversity_steps", 0)),
            "initial_diversity_fallback_used": bool(
                info.get("initial_diversity_fallback_used", False)
            ),
            "initial_diversity_fallback_reason": info.get(
                "initial_diversity_fallback_reason"
            ),
        }

    def _eds_validate_initial_cache_metadata(self, metadata: dict | None, cfg: _EDSConfig) -> None:
        if not cfg.initial_cache_metadata:
            return
        if metadata is None:
            log.warning(
                "EDS initial_population_cache has no metadata; assuming legacy cache "
                f"for initial_sampling_mode={cfg.initial_sampling_mode}"
            )
            return
        cached_mode = metadata.get("initial_sampling_mode")
        if cached_mode != cfg.initial_sampling_mode:
            raise ValueError(
                "EDS initial_population_cache initial_sampling_mode mismatch: "
                f"cache={cached_mode!r} config={cfg.initial_sampling_mode!r}"
            )
```

- [ ] **Step 5: Add iid helper**

Add:

```python
    def _eds_initial_denoise_iid(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
    ) -> tuple[Tensor, dict]:
        del cfg
        population = x_t
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        with torch.no_grad():
            for t in scheduler.timesteps:
                model_output = self._dit(population, t, cond)
                population = scheduler.step(
                    model_output,
                    t,
                    population,
                ).prev_sample.to(dtype=x_t.dtype)
        return population, {"initial_diversity_steps": 0}
```

- [ ] **Step 6: Refactor `_eds_initial_population()` cache path**

Update cache load logic to keep raw payload and validate metadata:

```python
            cached_payload = torch.load(cache_path, map_location=x_t.device)
            metadata = None
            cached = cached_payload
            if isinstance(cached_payload, dict) and "initial_population" in cached_payload:
                cached = cached_payload["initial_population"]
                metadata = cached_payload.get("metadata")
            self._eds_validate_initial_cache_metadata(metadata, cfg)
```

When saving cache, use a dict payload:

```python
                metadata = self._eds_initial_cache_metadata(
                    cfg,
                    self._eds_empty_initial_sampler_info(cfg),
                )
                torch.save(
                    {"initial_population": population.detach().cpu(), "metadata": metadata},
                    cfg.initial_population_cache,
                )
```

If the existing `_save_eds_population_cache()` only saves a label/tensor dict, do not remove it. Add a small wrapper `_save_eds_initial_population_cache(population, cfg, info)` that calls `Path(...).parent.mkdir(...)` and `torch.save(...)` with metadata.

- [ ] **Step 7: Refactor non-cache path to use iid helper**

In `_eds_initial_population()` replace the current full denoise block with:

```python
        start = time.perf_counter()
        if cfg.initial_sampling_mode == "iid":
            population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
        else:
            population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
            info["initial_diversity_fallback_used"] = True
            info["initial_diversity_fallback_reason"] = (
                f"unimplemented initial_sampling_mode={cfg.initial_sampling_mode}"
            )
            log.warning(
                "EDS initial sampler fallback to iid: "
                f"{info['initial_diversity_fallback_reason']}"
            )
        population = self._apply_action_mask(population, cond)
        info = {**self._eds_empty_initial_sampler_info(cfg), **info}
        info["initial_sampler_latency_s"] = float(time.perf_counter() - start)
        self._last_eds_initial_sampler_info = info
```

This temporary fallback is replaced in Task 3.

- [ ] **Step 8: Run tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_initial_population_masks_cached_population \
       tests/test_rdt_steer.py::test_eds_initial_population_iid_mode_preserves_shape_and_mask \
       tests/test_rdt_steer.py::test_eds_initial_population_rejects_cache_strategy_mismatch \
       tests/test_rdt_steer.py::test_eds_initial_population_warns_for_legacy_cache_without_metadata -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "refactor: prepare EDS initial sampler dispatch"
```

---

## Task 3: RBF-Diverse Initial Denoising Path

**Files:**

- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing RBF path test**

Add:

```python
def test_eds_initial_population_rbf_diverse_uses_diversity_gradient(
    stub_steer, stub_adapter, monkeypatch
):
    from core.rdt_policy_steer import _EDSConfig

    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"diversity": 0}

    def fake_diversity(x_t):
        calls["diversity"] += 1
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)
    action_mask = torch.zeros(1, 1, 128)
    action_mask[0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
            initial_diversity_scale=2.0,
        ),
    )

    assert calls["diversity"] > 0
    assert tuple(population.shape) == (3, 64, 128)
    assert torch.count_nonzero(population[:, :, 0]) == 0
    assert torch.count_nonzero(population[:, :4, 39]) > 0
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert info["initial_diversity_steps"] > 0
    assert info["initial_diversity_fallback_used"] is False
```

- [ ] **Step 2: Add failing fallback warning test**

Add:

```python
def test_eds_initial_population_rbf_diverse_warns_and_fallbacks_to_iid(
    stub_steer, monkeypatch, caplog
):
    from core.rdt_policy_steer import _EDSConfig

    def no_diversity(_x_t):
        return None

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", no_diversity)
    action_mask = torch.ones(1, 1, 128)

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": action_mask},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )

    assert tuple(population.shape) == (3, 64, 128)
    assert "fallback" in caplog.text.lower()
    assert "rbf_diverse_denoise" in caplog.text
    info = stub_steer._last_eds_initial_sampler_info
    assert info["initial_diversity_fallback_used"] is True
    assert info["initial_diversity_fallback_reason"]
```

- [ ] **Step 3: Add failing nonfinite fallback test**

Add:

```python
def test_eds_initial_population_rbf_diverse_nonfinite_gradient_fallbacks(
    stub_steer, monkeypatch, caplog
):
    from core.rdt_policy_steer import _EDSConfig

    def bad_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[0, 0, 39] = float("nan")
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", bad_diversity)

    population = stub_steer._eds_initial_population(
        x_t=torch.zeros(3, 64, 128),
        cond={"action_mask": torch.ones(1, 1, 128)},
        cfg=_EDSConfig(
            population_size=3,
            initial_sampling_mode="rbf_diverse_denoise",
        ),
    )

    assert torch.isfinite(population).all()
    assert "non-finite" in caplog.text.lower()
    assert stub_steer._last_eds_initial_sampler_info["initial_diversity_fallback_used"] is True
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_uses_diversity_gradient \
       tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_warns_and_fallbacks_to_iid \
       tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_nonfinite_gradient_fallbacks -q
```

Expected: FAIL because RBF path still uses temporary iid fallback.

- [ ] **Step 5: Add fallback helper**

In `core/rdt_policy_steer.py`, add:

```python
    def _eds_initial_fallback_to_iid(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
        reason: str,
    ) -> tuple[Tensor, dict]:
        log.warning(
            "EDS initial sampler fallback to iid: "
            f"initial_sampling_mode={cfg.initial_sampling_mode} reason={reason} "
            f"population_shape={tuple(x_t.shape)}"
        )
        population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
        info = {**self._eds_empty_initial_sampler_info(cfg), **info}
        info["initial_diversity_fallback_used"] = True
        info["initial_diversity_fallback_reason"] = reason
        return population, info
```

- [ ] **Step 6: Add RBF-diverse helper**

Add:

```python
    def _eds_initial_denoise_rbf_diverse(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        cfg: _EDSConfig,
    ) -> tuple[Tensor, dict]:
        if x_t.shape[0] <= 1:
            return self._eds_initial_fallback_to_iid(
                x_t=x_t,
                cond=cond,
                cfg=cfg,
                reason="population_size<=1",
            )

        population = x_t
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        start_step = self._resolve_start_step(
            scheduler.timesteps,
            cfg.initial_diversity_start_ratio,
        )
        grad_norms: list[float] = []
        grad_failures = 0
        diversity_steps = 0

        for i, t in enumerate(scheduler.timesteps):
            with torch.no_grad():
                model_output = self._dit(population, t, cond)

            if int(t.item()) > start_step:
                div_grad = self._compute_diversity_gradient(population)
                if div_grad is None:
                    grad_failures += 1
                    return self._eds_initial_fallback_to_iid(
                        x_t=x_t,
                        cond=cond,
                        cfg=cfg,
                        reason=f"diversity_gradient_none_at_step={i}_t={int(t.item())}",
                    )
                if not torch.isfinite(div_grad).all():
                    grad_failures += 1
                    return self._eds_initial_fallback_to_iid(
                        x_t=x_t,
                        cond=cond,
                        cfg=cfg,
                        reason=f"non-finite_diversity_gradient_at_step={i}_t={int(t.item())}",
                    )

                masked_div = self._mask_guidance_gradient(div_grad).to(
                    device=model_output.device,
                    dtype=model_output.dtype,
                )
                grad_norms.append(float(masked_div.detach().norm().cpu().item()))
                model_output[:, :, RDT_GUIDED_TRANSLATION_INDICES] += (
                    RDT_DIVERSITY_SIGN
                    * float(cfg.initial_diversity_scale)
                    * masked_div[:, :, RDT_GUIDED_TRANSLATION_INDICES]
                )
                diversity_steps += 1

            if not torch.isfinite(model_output).all():
                return self._eds_initial_fallback_to_iid(
                    x_t=x_t,
                    cond=cond,
                    cfg=cfg,
                    reason=f"non-finite_model_output_at_step={i}_t={int(t.item())}",
                )
            population = scheduler.step(model_output, t, population).prev_sample.to(
                dtype=x_t.dtype
            )
            if not torch.isfinite(population).all():
                return self._eds_initial_fallback_to_iid(
                    x_t=x_t,
                    cond=cond,
                    cfg=cfg,
                    reason=f"non-finite_population_at_step={i}_t={int(t.item())}",
                )

        info = self._eds_empty_initial_sampler_info(cfg)
        info["initial_diversity_steps"] = diversity_steps
        info["initial_diversity_grad_failure_count"] = grad_failures
        if grad_norms:
            info["initial_diversity_grad_norm_mean"] = float(sum(grad_norms) / len(grad_norms))
            info["initial_diversity_grad_norm_max"] = float(max(grad_norms))
        return population, info
```

- [ ] **Step 7: Dispatch RBF path**

In `_eds_initial_population()`, replace temporary fallback dispatch with:

```python
        if cfg.initial_sampling_mode == "iid":
            population, info = self._eds_initial_denoise_iid(x_t=x_t, cond=cond, cfg=cfg)
        elif cfg.initial_sampling_mode == "rbf_diverse_denoise":
            population, info = self._eds_initial_denoise_rbf_diverse(
                x_t=x_t,
                cond=cond,
                cfg=cfg,
            )
        else:
            raise ValueError(f"Unsupported EDS initial_sampling_mode={cfg.initial_sampling_mode!r}")
```

- [ ] **Step 8: Run RBF tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_uses_diversity_gradient \
       tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_warns_and_fallbacks_to_iid \
       tests/test_rdt_steer.py::test_eds_initial_population_rbf_diverse_nonfinite_gradient_fallbacks -q
```

Expected: PASS.

- [ ] **Step 9: Run focused initial population suite**

Run:

```bash
pytest tests/test_rdt_steer.py -k "eds_config or eds_initial_population" -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add RBF-diverse EDS initial sampler"
```

---

## Task 4: Initial Sampler Metrics

**Files:**

- Modify: `core/eds_eval_metrics.py`
- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_eds_eval_metrics.py`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing metrics serialization test**

Add to `tests/test_eds_eval_metrics.py`:

```python
def test_eds_chunk_metrics_serializes_initial_sampler_fields():
    metrics = EDSChunkMetrics(
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=1.0,
        initial_diversity_steps=3,
        initial_diversity_grad_norm_mean=0.5,
        initial_diversity_grad_norm_max=1.0,
        initial_diversity_grad_failure_count=0,
        initial_diversity_fallback_used=False,
        initial_diversity_fallback_reason=None,
        initial_sampler_latency_s=0.25,
    )

    payload = metrics.to_jsonable()

    assert payload["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert payload["initial_diversity_steps"] == 3
    assert payload["initial_sampler_latency_s"] == 0.25
```

- [ ] **Step 2: Add failing EDS loop metrics test**

Add to `tests/test_rdt_steer.py`:

```python
def test_eds_loop_records_initial_sampler_metrics(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
            "initial_diversity_scale": 1.0,
        },
        guidance_fns=[lambda keypoints, traj: torch.sum(traj[:, -1, 0])],
        keypoints=np.array([[0.0, 0.0, 0.0]], dtype=np.float32),
    )

    metrics = stub_steer.get_last_eds_metrics()

    assert metrics["initial_sampling_mode"] == "rbf_diverse_denoise"
    assert metrics["initial_diversity_steps"] > 0
    assert metrics["initial_diversity_fallback_used"] is False
    assert metrics["initial_sampler_latency_s"] is not None
```

- [ ] **Step 3: Run failing tests**

Run:

```bash
pytest tests/test_eds_eval_metrics.py::test_eds_chunk_metrics_serializes_initial_sampler_fields \
       tests/test_rdt_steer.py::test_eds_loop_records_initial_sampler_metrics -q
```

Expected: FAIL because metrics dataclass and EDS loop do not expose fields.

- [ ] **Step 4: Add metrics fields**

In `core/eds_eval_metrics.py`, add to `EDSChunkMetrics`:

```python
    initial_sampling_mode: str = "iid"
    initial_diversity_scale: float | None = None
    initial_diversity_start_ratio: float | None = None
    initial_diversity_steps: int = 0
    initial_diversity_grad_norm_mean: float | None = None
    initial_diversity_grad_norm_max: float | None = None
    initial_diversity_grad_failure_count: int = 0
    initial_diversity_fallback_used: bool = False
    initial_diversity_fallback_reason: str | None = None
    initial_sampler_latency_s: float | None = None
```

- [ ] **Step 5: Populate metrics after initial population**

In `_eds_guided_denoise_loop()`, immediately after:

```python
        population = self._eds_initial_population(x_t=x_t, cond=cond, cfg=cfg)
```

add:

```python
        initial_sampler_info = getattr(self, "_last_eds_initial_sampler_info", None) or {}
        metrics.initial_sampling_mode = str(
            initial_sampler_info.get("initial_sampling_mode", cfg.initial_sampling_mode)
        )
        metrics.initial_diversity_scale = float(cfg.initial_diversity_scale)
        metrics.initial_diversity_start_ratio = cfg.initial_diversity_start_ratio
        metrics.initial_diversity_steps = int(
            initial_sampler_info.get("initial_diversity_steps", 0)
        )
        metrics.initial_diversity_grad_norm_mean = initial_sampler_info.get(
            "initial_diversity_grad_norm_mean"
        )
        metrics.initial_diversity_grad_norm_max = initial_sampler_info.get(
            "initial_diversity_grad_norm_max"
        )
        metrics.initial_diversity_grad_failure_count = int(
            initial_sampler_info.get("initial_diversity_grad_failure_count", 0)
        )
        metrics.initial_diversity_fallback_used = bool(
            initial_sampler_info.get("initial_diversity_fallback_used", False)
        )
        metrics.initial_diversity_fallback_reason = initial_sampler_info.get(
            "initial_diversity_fallback_reason"
        )
        metrics.initial_sampler_latency_s = initial_sampler_info.get(
            "initial_sampler_latency_s"
        )
```

- [ ] **Step 6: Run metrics tests**

Run:

```bash
pytest tests/test_eds_eval_metrics.py::test_eds_chunk_metrics_serializes_initial_sampler_fields \
       tests/test_rdt_steer.py::test_eds_loop_records_initial_sampler_metrics -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add core/eds_eval_metrics.py core/rdt_policy_steer.py tests/test_eds_eval_metrics.py tests/test_rdt_steer.py
git commit -m "feat: record EDS initial sampler metrics"
```

---

## Task 5: Mechanism Trace Stages and Visualization

**Files:**

- Modify: `core/eds_mechanism_trace.py`
- Modify: `core/rdt_policy_steer.py`
- Modify: `utils/eds_mechanism_pretest_vis.py`
- Modify: `tests/test_eds_mechanism_trace.py`
- Modify: `tests/test_eds_mechanism_pretest_vis.py`
- Modify: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing trace metadata test**

Add to `tests/test_eds_mechanism_trace.py`:

```python
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
```

- [ ] **Step 2: Add failing visualization stage test**

In `tests/test_eds_mechanism_pretest_vis.py`, extend `_trace()` stages with:

```python
        EDSParticleStage(
            stage="initial_before_diversity",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.zeros(2, 2, 3),
            rewards=torch.tensor([0.0, 0.0]),
            costs=torch.tensor([0.0, 0.0]),
        ),
        EDSParticleStage(
            stage="initial_after_diversity_phase",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.ones(2, 2, 3),
            rewards=torch.tensor([0.0, 0.0]),
            costs=torch.tensor([0.0, 0.0]),
        ),
        EDSParticleStage(
            stage="initial_final",
            iter_idx=0,
            actions=torch.zeros(2, 64, 128),
            trajectories=torch.ones(2, 2, 3) * 2.0,
            rewards=torch.tensor([0.1, 0.2]),
            costs=torch.tensor([-0.1, -0.2]),
        ),
```

Then add:

```python
def test_save_eds_mechanism_pretest_artifacts_writes_initial_sampler_stage_pngs(tmp_path):
    save_eds_mechanism_pretest_artifacts(tmp_path, _trace())

    assert (
        tmp_path / "single_step_inner_loop" / "initial_before_diversity_3d.png"
    ).exists()
    assert (
        tmp_path / "single_step_inner_loop" / "initial_after_diversity_phase_3d.png"
    ).exists()
    assert (tmp_path / "single_step_inner_loop" / "initial_final_3d.png").exists()
```

- [ ] **Step 3: Add failing RDT trace stage test**

Add to `tests/test_rdt_steer.py`:

```python
def test_eds_mechanism_trace_records_rbf_initial_sampler_stages(
    stub_steer, stub_adapter, mock_batch, monkeypatch
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_diversity(x_t):
        grad = torch.zeros_like(x_t)
        grad[:, :4, 39] = torch.tensor([0.0, 1.0, -1.0]).view(3, 1)
        return grad

    monkeypatch.setattr(stub_steer, "_compute_diversity_gradient", fake_diversity)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        keypoints=np.zeros((1, 3), dtype=np.float32),
        guidance_fns=[lambda keypoints, traj: -torch.linalg.norm(traj[:, -1, :3], dim=-1).sum()],
        eds_config={
            "population_size": 3,
            "cem_iters": 1,
            "temperature": 0.1,
            "initial_sampling_mode": "rbf_diverse_denoise",
            "mechanism_pretest": {
                "enabled": True,
                "first_chunk_only": True,
                "save_single_step": True,
                "save_full_process": True,
                "save_tensors": True,
                "plot_3d": False,
                "max_full_process_iters": 1,
            },
        },
        global_step=0,
    )

    trace = stub_steer.get_last_eds_mechanism_trace()
    stages = {stage.stage for stage in trace.stages}

    assert "initial_before_diversity" in stages
    assert "initial_after_diversity_phase" in stages
    assert "initial_final" in stages
    assert trace.initial_sampler_info["initial_sampling_mode"] == "rbf_diverse_denoise"
```

- [ ] **Step 4: Run failing tests**

Run:

```bash
pytest tests/test_eds_mechanism_trace.py::test_save_mechanism_trace_records_initial_sampler_metadata \
       tests/test_eds_mechanism_pretest_vis.py::test_save_eds_mechanism_pretest_artifacts_writes_initial_sampler_stage_pngs \
       tests/test_rdt_steer.py::test_eds_mechanism_trace_records_rbf_initial_sampler_stages -q
```

Expected: FAIL because trace metadata and new stages are not wired.

- [ ] **Step 5: Add trace metadata field**

In `core/eds_mechanism_trace.py`, add to `EDSMechanismTrace`:

```python
    initial_sampler_info: dict[str, Any] = field(default_factory=dict)
```

Add to `_metadata_payload(trace)`:

```python
        "initial_sampler_info": trace.initial_sampler_info,
```

No special tensor serialization is needed because `_tensor_payload()` already embeds `_metadata_payload(trace)`.

- [ ] **Step 6: Add visualization filenames**

In `utils/eds_mechanism_pretest_vis.py`, extend `STAGE_FILENAMES`:

```python
    "initial_before_diversity": "initial_before_diversity_3d.png",
    "initial_after_diversity_phase": "initial_after_diversity_phase_3d.png",
    "initial_final": "initial_final_3d.png",
```

In `_plot_final_selected_vs_initial_best()`, replace initial lookup with:

```python
    initial = next(
        (
            stage
            for stage in trace.stages
            if stage.stage in {"initial_final", "initial"}
        ),
        None,
    )
```

- [ ] **Step 7: Capture initial trace stages in sampler**

In `core/rdt_policy_steer.py`, add a field assignment in `_eds_initial_population()`:

```python
        self._last_eds_initial_sampler_trace_stages = []
```

At the start of `_eds_initial_denoise_rbf_diverse()`, initialize:

```python
        trace_stages: list[tuple[str, Tensor]] = [
            ("initial_before_diversity", population.detach())
        ]
        recorded_after_diversity = False
```

Immediately when the first non-diversity timestep is reached after at least one diversity step, record:

```python
            if int(t.item()) <= start_step and diversity_steps > 0 and not recorded_after_diversity:
                trace_stages.append(("initial_after_diversity_phase", population.detach()))
                recorded_after_diversity = True
```

After denoising finishes, before returning:

```python
        if diversity_steps > 0 and not recorded_after_diversity:
            trace_stages.append(("initial_after_diversity_phase", population.detach()))
        trace_stages.append(("initial_final", population.detach()))
        self._last_eds_initial_sampler_trace_stages = trace_stages
```

In `_eds_initial_fallback_to_iid()`, set:

```python
        self._last_eds_initial_sampler_trace_stages = []
```

- [ ] **Step 8: Convert sampler trace tensors into `EDSParticleStage`**

In `_eds_guided_denoise_loop()`, after `trace_stages` is initialized and after `population_scores` / `population_info` are available, prepend initial sampler stages when `trace_enabled`:

```python
        if trace_enabled:
            rewards_for_initial = self._eds_rewards_from_info(
                population_scores,
                population_info,
            )
            costs_for_initial = population_scores
            for stage_name, stage_population in getattr(
                self,
                "_last_eds_initial_sampler_trace_stages",
                [],
            ):
                stage_population = self._apply_action_mask(
                    stage_population.to(device=population.device, dtype=population.dtype),
                    cond,
                )
                trace_stages.append(
                    self._eds_make_trace_stage(
                        stage=stage_name,
                        iter_idx=0,
                        population=stage_population,
                        costs=costs_for_initial,
                        info={"rewards": rewards_for_initial},
                    )
                )
```

Then keep existing `"initial"` and `"scored"` stages unchanged. This keeps old visualization filenames while adding RBF-specific stage plots.

When constructing `EDSMechanismTrace`, pass:

```python
                initial_sampler_info=dict(initial_sampler_info),
```

- [ ] **Step 9: Run trace tests**

Run:

```bash
pytest tests/test_eds_mechanism_trace.py::test_save_mechanism_trace_records_initial_sampler_metadata \
       tests/test_eds_mechanism_pretest_vis.py::test_save_eds_mechanism_pretest_artifacts_writes_initial_sampler_stage_pngs \
       tests/test_rdt_steer.py::test_eds_mechanism_trace_records_rbf_initial_sampler_stages -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add core/eds_mechanism_trace.py core/rdt_policy_steer.py utils/eds_mechanism_pretest_vis.py tests/test_eds_mechanism_trace.py tests/test_eds_mechanism_pretest_vis.py tests/test_rdt_steer.py
git commit -m "feat: trace RBF-diverse EDS initial sampling"
```

---

## Task 6: Runner Support and Evidence Protocol

**Files:**

- Modify: `scripts/rdt_eds_mechanism_pretest_runner.py`
- Modify: `scripts/rdt_eds_eval_runner.py`
- Modify: `tests/test_eds_mechanism_pretest_runner.py`
- Modify: `tests/test_eds_eval_runner.py`
- Create: `docs/03_evidence/eds_init_pg_diverse_sampling/README.md`

- [ ] **Step 1: Add failing mechanism runner command test**

Add to `tests/test_eds_mechanism_pretest_runner.py`:

```python
def test_build_pretest_command_can_enable_rbf_diverse_initial_sampler():
    runner = _load_runner()
    cmd = runner.build_pretest_command(
        reward_mode="normal",
        output_root=Path("outputs/pretest"),
        initial_sampling_mode="rbf_diverse_denoise",
        initial_diversity_scale=1.0,
        initial_diversity_start_ratio=None,
    )

    assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
    assert "main.eds_config.initial_diversity_scale=1.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=null" in cmd
```

- [ ] **Step 2: Add failing eval runner command test**

Add to `tests/test_eds_eval_runner.py`:

```python
def test_level4_jobs_include_rbf_diverse_initial_sampler_variant():
    runner = _load_runner()

    jobs = runner.build_jobs("level4", episodes=10)
    labels = {job["label"] for job in jobs}

    assert "eds_rbf_diverse_initial" in labels
    rbf_job = next(job for job in jobs if job["label"] == "eds_rbf_diverse_initial")
    assert rbf_job["initial_sampling_mode"] == "rbf_diverse_denoise"


def test_rbf_diverse_eval_command_sets_initial_sampler_overrides():
    runner = _load_runner()
    job = {
        "job_id": "level4_libero_object_swap_eds_rbf_diverse_initial",
        "suite": "libero_object_swap",
        "label": "eds_rbf_diverse_initial",
        "method": "eds_rbf_diverse_initial",
        "episodes": 3,
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        "renoise_t_max": 5,
        "renoise_t_min": 1,
        "reward_mode": "normal",
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 1.0,
        "initial_diversity_start_ratio": None,
    }

    cmd = runner.build_main_command(job, gpu="3", timeout_seconds=120)

    assert "main.eds_config.initial_sampling_mode=rbf_diverse_denoise" in cmd
    assert "main.eds_config.initial_diversity_scale=1.0" in cmd
    assert "main.eds_config.initial_diversity_start_ratio=null" in cmd
```

- [ ] **Step 3: Run failing runner tests**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_runner.py::test_build_pretest_command_can_enable_rbf_diverse_initial_sampler \
       tests/test_eds_eval_runner.py::test_level4_jobs_include_rbf_diverse_initial_sampler_variant \
       tests/test_eds_eval_runner.py::test_rbf_diverse_eval_command_sets_initial_sampler_overrides -q
```

Expected: FAIL because runners do not yet expose initial sampler overrides.

- [ ] **Step 4: Update mechanism pretest runner**

In `scripts/rdt_eds_mechanism_pretest_runner.py`, change function signature:

```python
def build_pretest_command(
    *,
    reward_mode: str,
    output_root: Path,
    initial_sampling_mode: str = "iid",
    initial_diversity_scale: float = 1.0,
    initial_diversity_start_ratio: str | None = None,
) -> list[str]:
```

Add command overrides after `main.eds_config.use_cem=false`:

```python
        f"main.eds_config.initial_sampling_mode={initial_sampling_mode}",
        f"main.eds_config.initial_diversity_scale={float(initial_diversity_scale)}",
        "main.eds_config.initial_diversity_start_ratio="
        + ("null" if initial_diversity_start_ratio is None else str(initial_diversity_start_ratio)),
```

Add parser args:

```python
    parser.add_argument("--initial-sampling-mode", default="iid")
    parser.add_argument("--initial-diversity-scale", type=float, default=1.0)
    parser.add_argument("--initial-diversity-start-ratio", default=None)
```

Pass them into `build_pretest_command()` and `build_control_commands()`.

- [ ] **Step 5: Update eval runner jobs**

In `scripts/rdt_eds_eval_runner.py`, add an EDS method entry for the RBF variant in the method list used by `build_jobs("level4", ...)`:

```python
    {
        "method": "eds_rbf_diverse_initial",
        "label": "eds_rbf_diverse_initial",
        "population_size": 16,
        "cem_iters": 10,
        "use_cem": False,
        "num_elites": 32,
        "temperature": 0.1,
        "renoise_t_max": 5,
        "renoise_t_min": 1,
        "reward_mode": "normal",
        "initial_sampling_mode": "rbf_diverse_denoise",
        "initial_diversity_scale": 1.0,
        "initial_diversity_start_ratio": None,
    },
```

Ensure unguided jobs do not get these overrides.

In `build_main_command()`, append for guided EDS jobs:

```python
                f"main.eds_config.initial_sampling_mode={job.get('initial_sampling_mode', 'iid')}",
                f"main.eds_config.initial_diversity_scale={job.get('initial_diversity_scale', 1.0)}",
                "main.eds_config.initial_diversity_start_ratio="
                + (
                    "null"
                    if job.get("initial_diversity_start_ratio") is None
                    else str(job.get("initial_diversity_start_ratio"))
                ),
```

- [ ] **Step 6: Update eval report aggregation**

In `scripts/rdt_eds_eval_runner.py`, when parsing metrics in `write_level4_report()`, include:

```python
        initial_sampler_latency_values = [
            float(record["initial_sampler_latency_s"])
            for record in metrics
            if isinstance(record.get("initial_sampler_latency_s"), (int, float))
        ]
        fallback_count = sum(
            1 for record in metrics if record.get("initial_diversity_fallback_used") is True
        )
```

Add columns:

```python
"initial_sampler_latency_mean"
"initial_fallback_count"
```

And include them in the markdown table. The exact column names should be:

```markdown
| Suite | Method | Complete | Success | SR | Select Latency Mean | EDS Latency Mean | Initial Sampler Latency Mean | Initial Fallback Count | Videos | Metrics | Qual PNG |
```

- [ ] **Step 7: Create evidence README**

Create `docs/03_evidence/eds_init_pg_diverse_sampling/README.md`:

```markdown
# EDS RBF-Diverse Initial Sampling Evidence

This directory stores reports for `initial_sampling_mode="rbf_diverse_denoise"`.

Every report must record:

- branch and commit hash;
- worktree path;
- exact command;
- full config overrides;
- sweep id and validation gate pass/fail;
- `CUDA_VISIBLE_DEVICES`, physical GPU id, and pre-run `nvidia-smi` summary;
- task suite, task ids, seeds, and episode count;
- checkpoint and policy type;
- guidance type, reward mode, VLM/keypoint cache;
- initial sampling mode and diversity parameters;
- success count / total and success rate;
- per-episode results, failure notes, and video paths;
- `initial_sampler_latency_s` and `select_action_latency_s`;
- initial/final diversity, endpoint spread, selected reward, and target distance;
- fallback warning count and reasons;
- qualitative artifact paths;
- comparison against unguided RDT and current EDS iid baseline.
```

- [ ] **Step 8: Run runner tests**

Run:

```bash
pytest tests/test_eds_mechanism_pretest_runner.py \
       tests/test_eds_eval_runner.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add scripts/rdt_eds_mechanism_pretest_runner.py scripts/rdt_eds_eval_runner.py tests/test_eds_mechanism_pretest_runner.py tests/test_eds_eval_runner.py docs/03_evidence/eds_init_pg_diverse_sampling/README.md
git commit -m "feat: add RBF-diverse EDS evaluation runner support"
```

---

## Task 7: Full Regression and Static Verification

**Files:**

- No code changes unless a preceding task left a failure.

- [ ] **Step 1: Run focused unit suite**

Run:

```bash
pytest tests/test_rdt_steer.py \
       tests/test_eds_eval_metrics.py \
       tests/test_eds_mechanism_trace.py \
       tests/test_eds_mechanism_pretest_vis.py \
       tests/test_eds_mechanism_pretest_runner.py \
       tests/test_eds_eval_runner.py -q
```

Expected: PASS.

- [ ] **Step 2: Run import/startup smoke tests**

Run:

```bash
pytest tests/test_main_rdt_startup.py tests/test_env_adapters_imports.py -q
```

Expected: PASS.

- [ ] **Step 3: Verify VLS path did not change semantically**

Run:

```bash
git diff main...HEAD -- core/rdt_policy_steer.py | grep -n "_vls_guided_denoise_loop" || true
```

Expected: Either no output, or output only from context lines. If `_vls_guided_denoise_loop()` body changed, stop and inspect. Revert any accidental VLS semantic change before continuing.

- [ ] **Step 4: Verify no FPS implementation leaked into this branch**

Run:

```bash
grep -R "farthest\\|fps\\|oversample" -n core tests scripts configs docs/01_specs/eds-init-pg-diverse-sampling-design.md docs/04_plans/2026-07-04-eds-init-pg-diverse-sampling.md
```

Expected: no matches in `core/`, `tests/`, `scripts/`, or `configs/`. Matches in unrelated old docs are acceptable only outside this grep scope.

- [ ] **Step 5: Commit if verification changed docs or tests**

If Step 1-4 required fixes:

```bash
git add <changed-files>
git commit -m "test: verify RBF-diverse EDS initial sampler"
```

If there were no changes, do not create an empty commit.

---

## Task 8: Mechanism Qualitative Pretest

**Files:**

- Runtime artifacts only under `outputs/` and `docs/03_evidence/eds_init_pg_diverse_sampling/`.

- [ ] **Step 1: Check GPU availability**

Run:

```bash
nvidia-smi
```

Expected: identify an idle H200. Prefer GPU 3 when idle. If GPU 3 is busy and another GPU is idle, use the idle GPU. Record the chosen GPU and the `nvidia-smi` summary in the report.

- [ ] **Step 2: Print mechanism command**

Run:

```bash
CUDA_VISIBLE_DEVICES=3 python scripts/rdt_eds_mechanism_pretest_runner.py \
  --reward-mode normal \
  --initial-sampling-mode rbf_diverse_denoise \
  --initial-diversity-scale 1.0 \
  --output-root outputs/rdt_eds_mechanism_pretest_rbf \
  --dry-run
```

Expected: command contains:

```text
main.guidance_type=eds
main.eds_config.initial_sampling_mode=rbf_diverse_denoise
main.eds_config.initial_diversity_scale=1.0
main.eds_mechanism_pretest.enabled=true
```

- [ ] **Step 3: Run mechanism qualitative pretest**

Use the idle GPU chosen in Step 1:

```bash
CUDA_VISIBLE_DEVICES=3 python scripts/rdt_eds_mechanism_pretest_runner.py \
  --reward-mode normal \
  --initial-sampling-mode rbf_diverse_denoise \
  --initial-diversity-scale 1.0 \
  --output-root outputs/rdt_eds_mechanism_pretest_rbf
```

Expected:

- process exits 0;
- `initial_before_diversity_3d.png` exists;
- `initial_after_diversity_phase_3d.png` exists;
- `initial_final_3d.png` exists;
- `full_process_summary.md` exists;
- metrics JSONL contains `initial_sampling_mode="rbf_diverse_denoise"`;
- fallback warning count is 0.

- [ ] **Step 4: Write mechanism evidence note**

Create or update:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/mechanism_pretest_report.md
```

Include:

```markdown
# Mechanism Pretest Report

- Branch:
- Commit:
- Worktree:
- GPU:
- `CUDA_VISIBLE_DEVICES`:
- Pre-run `nvidia-smi` summary:
- Command:
- Output root:
- Initial sampler:
- Diversity scale:
- Fallback warnings:
- Initial trajectory diversity:
- Endpoint spread:
- Selected reward:
- Target distance:
- Qualitative artifacts:
- Verdict:
- Debug notes:
```

Fill every bullet with the run result. If a field is unavailable in current artifacts, write `not recorded by current runner` and open a follow-up issue before full OOD eval.

- [ ] **Step 5: Commit evidence report**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/mechanism_pretest_report.md
git commit -m "docs: record RBF-diverse EDS mechanism pretest"
```

---

## Task 9: Closed-Loop Parameter Sweep

**Files:**

- Runtime artifacts under `outputs/`.
- Reports under `docs/03_evidence/eds_init_pg_diverse_sampling/`.

- [ ] **Step 1: Establish iid baseline smoke**

Use an idle GPU:

```bash
nvidia-smi
CUDA_VISIBLE_DEVICES=3 python scripts/rdt_eds_eval_runner.py run-level \
  --level level2 \
  --episodes 3 \
  --gpus 3 \
  --timeout-seconds 28800 \
  --resume
```

Expected: runner produces non-empty `outputs/rdt_eds_eval/.../eds_eval/eds_metrics.jsonl` for iid EDS jobs.

- [ ] **Step 2: Run RBF default smoke**

Use the runner configuration from Task 6. If `run-level level2` does not yet include `eds_rbf_diverse_initial`, add it in Task 6 before this step.

```bash
CUDA_VISIBLE_DEVICES=3 python scripts/rdt_eds_eval_runner.py run-level \
  --level level2 \
  --episodes 3 \
  --gpus 3 \
  --timeout-seconds 28800 \
  --resume
```

Expected:

- RBF job exits 0;
- fallback count is 0;
- `initial_sampler_latency_s` is recorded;
- initial trajectory diversity and endpoint spread exceed iid baseline;
- selected reward is not lower than iid baseline;
- final target distance is not worse than iid baseline.

- [ ] **Step 3: Sweep only initial sampler parameters if default fails**

Allowed initial sampler sweep grid:

```text
initial_diversity_scale: [0.25, 0.5, 1.0, 2.0]
initial_diversity_start_ratio: [null, 0.25, 0.5]
population_size: [16, 32]
```

Run one configuration per idle GPU. Prefer GPU 3 first; use other H200 cards only if `nvidia-smi` shows they are idle. Each job must have a unique output directory and seed.

Record each attempt in:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/parameter_sweep.md
```

Use this table:

```markdown
| Sweep ID | GPU | Command | Scale | Start Ratio | Population | Fallback Count | Diversity Gate | Endpoint Gate | Reward Gate | Distance Gate | Latency Gate | Verdict |
|---|---:|---|---:|---:|---:|---:|---|---|---|---|---|---|
```

- [ ] **Step 4: Sweep EDS refinement only if initial metrics pass**

Only after initial diversity and endpoint gates pass, sweep existing EDS refinement knobs:

```text
cem_iters: [10, 20]
temperature: [0.1, 0.5, 1.0]
renoise_t_max: [3, 5]
renoise_t_min: [1]
num_elites: [8, 16, 32]  # only when use_cem=true and num_elites<=population_size
```

Do not change:

- RBF distance space;
- diversity sign;
- translation slot list;
- reward function;
- EDS loop semantics.

- [ ] **Step 5: Stop criteria**

Stop the sweep when all gates pass:

- shape, finite, and action mask violation pass;
- fallback warning count is 0;
- initial trajectory diversity exceeds iid baseline;
- endpoint spread exceeds iid baseline;
- selected reward is not lower than iid baseline;
- final target distance is not worse than iid baseline;
- OOD success rate is non-zero and higher than current EDS baseline;
- `initial_sampler_latency_s` and total `select_action_latency_s` are acceptable.

If no sweep configuration passes, write a failure report and request approval before changing algorithm logic.

- [ ] **Step 6: Commit sweep report**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/parameter_sweep.md
git commit -m "docs: record RBF-diverse EDS parameter sweep"
```

---

## Task 10: Full OOD Evaluation and Final Report

**Files:**

- Runtime artifacts under `outputs/`.
- Reports under `docs/03_evidence/eds_init_pg_diverse_sampling/`.

- [ ] **Step 1: Select final candidate config**

From `parameter_sweep.md`, pick the first passing config by this priority:

1. no fallback;
2. highest OOD success rate;
3. selected reward not below baseline;
4. final target distance not worse than baseline;
5. lower `select_action_latency_s`;
6. lower `initial_sampler_latency_s`.

Record the selected config in:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/final_config.md
```

- [ ] **Step 2: Run full OOD groups**

Use these control groups:

- unguided RDT;
- current EDS iid baseline;
- EDS + RBF-diverse initial sampler.

Use these task suites:

- `libero_object_swap`;
- `libero_object_task`;
- `libero_object_task`.

If the two `libero_object_task` entries correspond to different task ids or OOD splits, record exact task ids and split identifiers.

Run with idle GPUs:

```bash
nvidia-smi
CUDA_VISIBLE_DEVICES=3 python scripts/rdt_eds_eval_runner.py run-level \
  --level level4 \
  --episodes 10 \
  --gpus 3 \
  --timeout-seconds 28800 \
  --resume
```

If multiple H200 cards are idle, use:

```bash
python scripts/rdt_eds_eval_runner.py run-level \
  --level level4 \
  --episodes 10 \
  --gpus 3,2 \
  --timeout-seconds 28800 \
  --resume
```

Only include GPUs that are idle according to `nvidia-smi`.

- [ ] **Step 3: Generate runner report**

Run:

```bash
python scripts/rdt_eds_eval_runner.py write-level4-report --episodes 10
```

Expected: report includes success rate, latency, metrics count, initial sampler latency, and fallback count for RBF jobs.

- [ ] **Step 4: Write final experiment report**

Create:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/final_ood_evaluation_report.md
```

Use this structure:

```markdown
# Final OOD Evaluation Report

## Run Metadata

- Branch:
- Commit:
- Worktree:
- Date:
- GPUs:
- `nvidia-smi` summaries:
- Exact commands:
- Output roots:

## Configs

- Unguided RDT:
- Current EDS iid baseline:
- EDS + RBF-diverse initial sampler:

## Tasks

| Suite | Task IDs | Seeds | Episodes |
|---|---|---|---:|

## Results

| Method | Suite | Success / Total | Success Rate | Initial Diversity | Endpoint Spread | Selected Reward | Final Target Distance | Initial Sampler Latency | Select Action Latency | Fallback Warnings |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|

## Validation Gates

| Gate | Status | Evidence |
|---|---|---|
| OOD success rate non-zero |  |  |
| OOD success rate higher than current EDS baseline |  |  |
| Initial trajectory diversity higher than baseline |  |  |
| Endpoint spread higher than baseline |  |  |
| Selected reward not below baseline |  |  |
| Final target distance not worse than baseline |  |  |
| Latency acceptable |  |  |
| Fallback count acceptable |  |  |

## Failure Analysis

- Per-episode failures:
- Video paths:
- Suspected failure modes:
- Debug priorities:

## Verdict

- Pass / fail / blocked:
- Reason:
```

- [ ] **Step 5: Commit final report**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/final_config.md docs/03_evidence/eds_init_pg_diverse_sampling/final_ood_evaluation_report.md
git commit -m "docs: report RBF-diverse EDS OOD evaluation"
```

---

## Task 11: Final Cleanup and Review Request

**Files:**

- No planned code changes.

- [ ] **Step 1: Run final tests**

Run:

```bash
pytest tests/test_rdt_steer.py \
       tests/test_eds_eval_metrics.py \
       tests/test_eds_mechanism_trace.py \
       tests/test_eds_mechanism_pretest_vis.py \
       tests/test_eds_mechanism_pretest_runner.py \
       tests/test_eds_eval_runner.py \
       tests/test_main_rdt_startup.py \
       tests/test_env_adapters_imports.py -q
```

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run:

```bash
git status --short
git diff --stat main...HEAD
git diff main...HEAD -- core/rdt_policy_steer.py core/eds_eval_metrics.py core/eds_mechanism_trace.py
```

Expected:

- no accidental VLS semantic edits;
- no FPS implementation;
- no unrelated files;
- docs/evidence files correspond to actual runs.

- [ ] **Step 3: Summarize implementation**

Create a review note in:

```text
docs/03_evidence/eds_init_pg_diverse_sampling/review_summary.md
```

Include:

```markdown
# Review Summary

- Feature:
- Branch:
- Commits:
- Tests run:
- Mechanism pretest verdict:
- OOD evaluation verdict:
- Known risks:
- Files changed:
- Reviewer focus:
  - RBF helper reuses VLS diversity semantics.
  - EDS refinement remains unchanged.
  - Cache metadata prevents iid/RBF mismatch.
  - Fallback warns and records metrics.
  - Metrics/reporting can debug OOD failures.
```

- [ ] **Step 4: Commit review note**

```bash
git add docs/03_evidence/eds_init_pg_diverse_sampling/review_summary.md
git commit -m "docs: summarize RBF-diverse EDS implementation"
```

- [ ] **Step 5: Request code review**

Use `superpowers:requesting-code-review` before opening a PR or asking for merge approval.

---

## Self-Review Checklist

- Spec coverage:
  - `initial_sampling_mode` is the only mechanism switch: Tasks 1, 3, 6.
  - No `initial_diversity_enabled`: Task 1 validation and file map.
  - No `initial_diversity_allow_grad`: Task 1 validation and file map.
  - VLS glue/reuse: Task 3 uses `_compute_diversity_gradient()`, `_mask_guidance_gradient()`, `RDT_DIVERSITY_SIGN`, and `RDT_GUIDED_TRANSLATION_INDICES`.
  - 3D EEF trajectory RBF space: Task 3 does not add another metric.
  - Warning fallback: Task 3 tests and helper.
  - No FPS oversampling: Task 7 grep gate.
  - Cache compatibility and metadata: Task 2.
  - Metrics and mechanism trace: Tasks 4 and 5.
  - Qualitative evaluation: Task 8.
  - Full OOD evaluation: Task 10.
  - Closed-loop sweep: Task 9.
  - H200 idle GPU policy: Tasks 8-10.

- Placeholder scan:
  - No `TBD`.
  - No unbounded "add appropriate handling" instructions.
  - Every code task includes concrete test snippets, implementation snippets, commands, and expected outcomes.

- Type consistency:
  - Config field names match design: `initial_sampling_mode`, `initial_diversity_scale`, `initial_diversity_start_ratio`, `initial_diversity_fallback`, `initial_cache_metadata`.
  - Metrics field names match report requirements.
  - Trace field name is `initial_sampler_info` in dataclass and metadata.

