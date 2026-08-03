# RDT EDS Guidance Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add EDS as a peer RDT guidance mode beside VLS, using grouped policy-independent steering configs and VLS-style `cond once + action population batch + forward expand` sampling.

**Architecture:** `main.py` owns policy-independent `main.guidance_type`, `main.vls_config`, and `main.eds_config`. `RDTSteer._predict_guided()` performs shared RDT input encoding once, then dispatches to `_vls_guided_denoise_loop()` or `_eds_guided_denoise_loop()`. EDS follows the `run_diffusion_es()` parameter semantics and core loop: initial population, score/cost, resample, renoise, rollout denoise, rescore, best-particle selection.

**Tech Stack:** Python, PyTorch, Hydra/OmegaConf YAML config, pytest CPU stubs, existing RDTSteer/RDTLibero converters.

---

## File Structure

- Modify `configs/config.yaml`
  - Add `main.guidance_type`, `main.vls_config`, and `main.eds_config`.
  - Read grouped steering configs from `main.vls_config` and `main.eds_config`.

- Modify `main.py`
  - Build grouped `vls_config` and `eds_config` from `self.config`.
  - Pass grouped configs to RDT policies.
  - Preserve legacy scattered VLS kwargs for non-RDT policies to avoid breaking PI0.5/DiffusionPolicy before they implement grouped steering.

- Modify `core/rdt_policy_steer.py`
  - Add `_EDSConfig` dataclass and config resolvers.
  - Change `RDTSteer.select_action()` and `_predict_guided()` to accept `guidance_type`, `vls_config`, and `eds_config`.
  - Rename `_guided_denoise_loop()` to `_vls_guided_denoise_loop()`.
  - Add `_eds_guided_denoise_loop()` and helper methods.
  - Keep EDS action population batch in `(B,64,128)` and keep `cond` batch at 1, relying on `_RDTDiTAdapter.forward()` to expand conditions.

- Modify `tests/test_rdt_steer.py`
  - Update existing guided tests to pass `vls_config`.
  - Add EDS routing, cost conversion, cond-once batch, renoise/rollout, selection, and visualization tests.
  - Extend `_StubScheduler` with `add_noise()` for EDS renoise tests.

- Do not modify `third_party/RoboticsDiffusionTransformer-diffusion-es`.

---

### Task 1: Config Schema and Main Routing

**Files:**
- Modify: `configs/config.yaml:35-55`
- Modify: `main.py:670-693`
- Test: manual Hydra/OmegaConf config load command

- [ ] **Step 1: Update config with grouped steering keys**

In `configs/config.yaml`, replace the current steering section under `main` with this grouped structure:

```yaml
  # Steering parameters
  use_guidance: false
  guidance_type: vls  # valid: vls, eds
  use_vlm_stage_recognition: true  # Use Gemini to recognize current stage
  vlm_query_limit: 50  # Max VLM queries per episode

  vls_config:
    use_diversity: true
    sample_batch_size: 20
    guide_scale: 40.0
    diversity_scale: 10.0
    start_ratio: null
    MCMC_steps: 4
    sigmoid_k: 25.0
    sigmoid_x0: 0.75
    use_fkd: true
    fkd:
      potential_type: max
      lmbda: 10.0
      adaptive_resampling: true
      resample_frequency: 5

  eds_config:
    population_size: 16
    use_cem: false
    cem_iters: 20
    num_elites: 32
    temperature: 0.1
    initial_population_cache: null
    ed_population_cache: null
    use_initial_cache: false
    save_initial_cache: false
    save_ed_cache: false
```

- [ ] **Step 2: Verify config keys can be loaded**

Run:

```bash
python - <<'PY'
from omegaconf import OmegaConf
cfg = OmegaConf.load("configs/config.yaml")
assert cfg.main.guidance_type == "vls"
assert cfg.main.vls_config.sample_batch_size == 20
assert cfg.main.eds_config.population_size == 16
assert cfg.main.eds_config.cem_iters == 20
print("grouped guidance config ok")
PY
```

Expected: prints `grouped guidance config ok`.

- [ ] **Step 3: Update `main.py` to build grouped configs**

Near `main.py:670`, replace scalar guidance parameter extraction with:

```python
            guidance_type = str(self.config.get("guidance_type", "vls")).lower()
            if guidance_type not in {"vls", "eds"}:
                raise ValueError(
                    f"Unsupported main.guidance_type={guidance_type!r}; "
                    "expected one of {'vls', 'eds'}"
                )

            vls_config = OmegaConf.to_container(
                self.config.get("vls_config", {}),
                resolve=True,
            )
            eds_config = OmegaConf.to_container(
                self.config.get("eds_config", {}),
                resolve=True,
            )
```

- [ ] **Step 4: Update `main.py` select_action kwargs**

Replace the direct `self.policy.select_action(...)` call at `main.py:675-693` with a kwargs block that keeps RDT grouped and non-RDT legacy-compatible:

```python
            select_kwargs = {
                "batch": observation,
                "generate_new_chunk": generate_new_chunk,
                "use_guidance": use_guidance,
                "keypoints": keypoints,
                "guidance_fns": current_guidance_fns,
                "verbose": True,
                "global_step": global_steps,
                "current_stage": current_stage,
            }

            if self.policy_type == "rdt":
                select_kwargs.update(
                    {
                        "guidance_type": guidance_type,
                        "vls_config": vls_config,
                        "eds_config": eds_config,
                    }
                )
            else:
                if guidance_type == "eds" and use_guidance:
                    raise ValueError(
                        "main.guidance_type=eds is currently implemented only for policy.type=rdt"
                    )
                select_kwargs.update(
                    {
                        "guide_scale": vls_config.get("guide_scale", 80.0),
                        "sigmoid_k": vls_config.get("sigmoid_k", 12.0),
                        "sigmoid_x0": vls_config.get("sigmoid_x0", 0.7),
                        "start_ratio": vls_config.get("start_ratio", None),
                        "use_diversity": vls_config.get("use_diversity", True),
                        "diversity_scale": vls_config.get("diversity_scale", 10.0),
                        "MCMC_steps": vls_config.get("MCMC_steps", 4),
                        "use_fkd": vls_config.get("use_fkd", False),
                        "fkd_config": vls_config.get("fkd", None),
                    }
                )

            action_chunk = self.policy.select_action(**select_kwargs)
```

- [ ] **Step 5: Run syntax check**

Run:

```bash
python -m py_compile main.py
```

Expected: exit code 0.

- [ ] **Step 6: Commit**

```bash
git add configs/config.yaml main.py
git commit -m "config: add grouped guidance configs"
```

---

### Task 2: RDT Grouped Guidance API and VLS Rename

**Files:**
- Modify: `core/rdt_policy_steer.py:940-1120`
- Modify: `core/rdt_policy_steer.py:1199-1309`
- Modify: `tests/test_rdt_steer.py:335-718`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Write failing routing tests**

Append these tests after `test_guided_select_action_uses_latent_particle_batch` in `tests/test_rdt_steer.py`:

```python
def test_rdt_guidance_type_vls_routes_to_vls_guided_denoise_loop(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"vls": 0, "eds": 0}

    def fake_vls(**kwargs):
        calls["vls"] += 1
        return torch.zeros(1, 64, 128)

    def fake_eds(**kwargs):
        calls["eds"] += 1
        return torch.zeros(1, 64, 128)

    monkeypatch.setattr(stub_steer, "_vls_guided_denoise_loop", fake_vls)
    monkeypatch.setattr(stub_steer, "_eds_guided_denoise_loop", fake_eds)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="vls",
        vls_config={"sample_batch_size": 4},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert calls == {"vls": 1, "eds": 0}


def test_rdt_guidance_type_eds_routes_to_eds_loop(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=4,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = {"vls": 0, "eds": 0}

    def fake_vls(**kwargs):
        calls["vls"] += 1
        return torch.zeros(1, 64, 128)

    def fake_eds(**kwargs):
        calls["eds"] += 1
        return torch.zeros(1, 64, 128)

    monkeypatch.setattr(stub_steer, "_vls_guided_denoise_loop", fake_vls)
    monkeypatch.setattr(stub_steer, "_eds_guided_denoise_loop", fake_eds)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 4, "cem_iters": 1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert calls == {"vls": 0, "eds": 1}


def test_rdt_guidance_type_invalid_raises_clear_error(stub_steer, stub_adapter, mock_batch):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    with pytest.raises(ValueError, match="Unsupported RDT guidance_type"):
        stub_steer.select_action(
            mock_batch,
            generate_new_chunk=True,
            use_guidance=True,
            guidance_type="bad",
            guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
            keypoints=np.zeros((3, 3), dtype=np.float32),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_rdt_guidance_type_vls_routes_to_vls_guided_denoise_loop \
       tests/test_rdt_steer.py::test_rdt_guidance_type_eds_routes_to_eds_loop \
       tests/test_rdt_steer.py::test_rdt_guidance_type_invalid_raises_clear_error -q
```

Expected: fail because `_vls_guided_denoise_loop`, `_eds_guided_denoise_loop`, and `guidance_type` routing do not exist yet.

- [ ] **Step 3: Add config resolver helpers**

In `core/rdt_policy_steer.py`, add this helper near constants:

```python
def _resolve_vls_config(vls_config: Optional[dict], *, default_sample_batch_size: int) -> dict:
    cfg = dict(vls_config or {})
    cfg.setdefault("sample_batch_size", default_sample_batch_size)
    cfg.setdefault("guide_scale", 1.0)
    cfg.setdefault("sigmoid_k", 12.0)
    cfg.setdefault("sigmoid_x0", 0.7)
    cfg.setdefault("start_ratio", None)
    cfg.setdefault("use_diversity", True)
    cfg.setdefault("diversity_scale", 1.0)
    cfg.setdefault("MCMC_steps", 4)
    cfg.setdefault("use_fkd", False)
    cfg.setdefault("fkd", None)
    return cfg
```

- [ ] **Step 4: Update `select_action()` signature and call**

Replace the scattered VLS parameters in `RDTSteer.select_action()` with grouped config params:

```python
    def select_action(
        self,
        batch: dict,
        generate_new_chunk: bool = False,
        use_guidance: bool = False,
        keypoints: Optional[np.ndarray] = None,
        guidance_fns: Optional[List[Callable]] = None,
        guidance_type: str = "vls",
        vls_config: Optional[dict] = None,
        eds_config: Optional[dict] = None,
        verbose: bool = False,
        global_step: int = 0,
        current_stage: int = 1,
    ) -> Tensor:
```

Inside the guided branch, call `_predict_guided()` with grouped configs:

```python
                raw = self._predict_guided(
                    converted.state_128,
                    converted.state_mask_128,
                    converted.images,
                    text_embed,
                    keypoints=keypoints,
                    guidance_fns=guidance_fns,
                    guidance_type=guidance_type,
                    vls_config=vls_config,
                    eds_config=eds_config,
                    verbose=verbose,
                    global_step=global_step,
                    current_stage=current_stage,
                )
```

- [ ] **Step 5: Update `_predict_guided()` dispatch**

Replace `_predict_guided()` signature with:

```python
    def _predict_guided(
        self,
        state_128: Tensor,
        state_mask_128: Tensor,
        images: list,
        text_embed: Tensor,
        *,
        keypoints: Optional[np.ndarray],
        guidance_fns: Optional[List[Callable]],
        guidance_type: str,
        vls_config: Optional[dict],
        eds_config: Optional[dict],
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
```

In `_predict_guided()`, after `unified_action_dim` validation, add:

```python
        guidance_type = str(guidance_type or "vls").lower()
        if guidance_type not in {"vls", "eds"}:
            raise ValueError(
                f"Unsupported RDT guidance_type={guidance_type!r}; expected 'vls' or 'eds'"
            )

        resolved_vls_config = _resolve_vls_config(
            vls_config,
            default_sample_batch_size=self._sample_batch_size,
        )
        resolved_eds_config = self._resolve_eds_config_with_reference_defaults(eds_config)
        if guidance_type == "vls":
            B = max(1, int(resolved_vls_config["sample_batch_size"]))
        else:
            B = max(1, int(resolved_eds_config.population_size))
```

Replace the old unconditional loop call with:

```python
        if guidance_type == "vls":
            guided = self._vls_guided_denoise_loop(
                x_t=x_t,
                cond=cond,
                keypoints=keypoints_tensor,
                guidance_fns=guidance_fns,
                vls_config=resolved_vls_config,
                verbose=verbose,
                global_step=global_step,
                current_stage=current_stage,
            )
        else:
            guided = self._eds_guided_denoise_loop(
                x_t=x_t,
                cond=cond,
                keypoints=keypoints_tensor,
                guidance_fns=guidance_fns,
                eds_config=resolved_eds_config,
                verbose=verbose,
                global_step=global_step,
                current_stage=current_stage,
            )
```

- [ ] **Step 6: Rename VLS loop and unpack config inside it**

Rename `_guided_denoise_loop()` to `_vls_guided_denoise_loop()` and replace its signature with:

```python
    def _vls_guided_denoise_loop(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        vls_config: dict,
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
```

At the start of the method, before `scheduler = self._noise_scheduler`, unpack:

```python
        guide_scale = float(vls_config.get("guide_scale", 1.0))
        sigmoid_k = float(vls_config.get("sigmoid_k", 12.0))
        sigmoid_x0 = float(vls_config.get("sigmoid_x0", 0.7))
        start_ratio = vls_config.get("start_ratio", None)
        use_diversity = bool(vls_config.get("use_diversity", True))
        diversity_scale = float(vls_config.get("diversity_scale", 1.0))
        MCMC_steps = int(vls_config.get("MCMC_steps", 4))
        use_fkd = bool(vls_config.get("use_fkd", False))
        fkd_config = vls_config.get("fkd", None)
```

- [ ] **Step 7: Update existing tests to pass `vls_config`**

For every existing guided call in `tests/test_rdt_steer.py` that currently passes `guide_scale`, `use_diversity`, `diversity_scale`, `use_fkd`, or `fkd_config`, move those fields into `vls_config`.

Example replacement:

```python
        guidance_type="vls",
        vls_config={
            "sample_batch_size": 4,
            "guide_scale": 1.0,
            "use_diversity": True,
            "diversity_scale": 1.0,
            "use_fkd": True,
            "fkd": {
                "potential_type": "max",
                "lmbda": 1.0,
                "adaptive_resampling": False,
                "resample_frequency": 1,
            },
        },
```

For guided calls that rely on defaults, add:

```python
        guidance_type="vls",
        vls_config={"sample_batch_size": 3},
```

- [ ] **Step 8: Add an EDS stub for the routing task**

Add this method after `_vls_guided_denoise_loop()` so routing tests have a callable EDS branch. Task 5 replaces this method with the full loop.

```python
    def _eds_guided_denoise_loop(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        eds_config,
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
        return x_t[0:1]
```

- [ ] **Step 9: Run RDT tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected: all tests pass after grouped API updates.

- [ ] **Step 10: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "refactor: route RDT guidance by grouped configs"
```

---

### Task 3: EDS Config Dataclass and Low-Level Helpers

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing helper tests**

Append these tests near the new EDS routing tests:

```python
def test_eds_config_defaults_match_reference_signature(stub_steer):
    cfg = stub_steer._resolve_eds_config_with_reference_defaults({})

    assert cfg.population_size == 16
    assert cfg.use_cem is False
    assert cfg.cem_iters == 20
    assert cfg.num_elites == 32
    assert cfg.temperature == 0.1
    assert cfg.use_initial_cache is False
    assert cfg.save_initial_cache is False
    assert cfg.save_ed_cache is False


def test_eds_config_rejects_invalid_cem_elites(stub_steer):
    with pytest.raises(ValueError, match="num_elites"):
        stub_steer._resolve_eds_config_with_reference_defaults(
            {"population_size": 4, "use_cem": True, "num_elites": 8}
        )


def test_trajectory_reward_slice_accepts_eds(stub_steer):
    trajs = torch.zeros(2, 5, 3)
    sliced = stub_steer._trajectory_reward_slice(trajs, "eds")
    assert tuple(sliced.shape) == (2, stub_steer._action_chunk_horizon - 1, 3)
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_config_defaults_match_reference_signature \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_cem_elites \
       tests/test_rdt_steer.py::test_trajectory_reward_slice_accepts_eds -q
```

Expected: fail because `_EDSConfig`, resolver, and `slice_kind="eds"` do not exist.

- [ ] **Step 3: Add dataclass import and `_EDSConfig`**

At the top of `core/rdt_policy_steer.py`, add:

```python
from dataclasses import dataclass
```

After constants, add:

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
```

- [ ] **Step 4: Implement EDS config resolver**

Add this method inside `RDTSteer`, near `_resolve_start_step()`:

```python
    def _resolve_eds_config_with_reference_defaults(self, eds_config: Optional[dict]) -> _EDSConfig:
        cfg = dict(eds_config or {})
        resolved = _EDSConfig(
            population_size=int(cfg.get("population_size", 16)),
            use_cem=bool(cfg.get("use_cem", False)),
            cem_iters=int(cfg.get("cem_iters", 20)),
            num_elites=int(cfg.get("num_elites", 32)),
            temperature=float(cfg.get("temperature", 0.1)),
            initial_population_cache=cfg.get("initial_population_cache", None),
            ed_population_cache=cfg.get("ed_population_cache", None),
            use_initial_cache=bool(cfg.get("use_initial_cache", False)),
            save_initial_cache=bool(cfg.get("save_initial_cache", False)),
            save_ed_cache=bool(cfg.get("save_ed_cache", False)),
        )
        if resolved.population_size <= 0:
            raise ValueError("EDS population_size must be positive")
        if resolved.cem_iters <= 0:
            raise ValueError("EDS cem_iters must be positive")
        if resolved.temperature <= 0:
            raise ValueError("EDS temperature must be positive")
        if resolved.use_cem and resolved.num_elites > resolved.population_size:
            raise ValueError(
                "EDS num_elites must be <= population_size when use_cem=true"
            )
        if resolved.use_cem and resolved.num_elites <= 0:
            raise ValueError("EDS num_elites must be positive when use_cem=true")
        return resolved
```

- [ ] **Step 5: Add EDS trajectory slice**

Update `_trajectory_reward_slice()`:

```python
        if slice_kind == "eds":
            return trajs[:, 1 : self._action_chunk_horizon, :3]
```

- [ ] **Step 6: Extend stub scheduler with `add_noise()`**

In `tests/test_rdt_steer.py`, update `_StubScheduler`:

```python
    def add_noise(self, original_samples, noise, timesteps):
        if torch.is_tensor(timesteps):
            scale = timesteps.to(device=original_samples.device, dtype=original_samples.dtype)
            while scale.ndim < original_samples.ndim:
                scale = scale.unsqueeze(-1)
            scale = scale / max(len(self.timesteps), 1)
        else:
            scale = float(timesteps) / max(len(self.timesteps), 1)
        return original_samples + noise * scale
```

- [ ] **Step 7: Run helper tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_config_defaults_match_reference_signature \
       tests/test_rdt_steer.py::test_eds_config_rejects_invalid_cem_elites \
       tests/test_rdt_steer.py::test_trajectory_reward_slice_accepts_eds -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add EDS config helpers"
```

---

### Task 4: EDS Population, RENOISE, Rollout, and Cost Scoring

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing EDS helper tests**

Append:

```python
def test_eds_direct_vls_reward_scoring_converts_to_cost_when_needed(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=3,
        policy_config={"action_chunk_horizon": 4},
    )
    samples = torch.zeros(3, 64, 128)
    monkeypatch.setattr(
        stub_steer,
        "_score_particles",
        lambda samples, keypoints, guidance_fns, slice_kind: torch.tensor([1.0, 3.0, 2.0]),
    )

    costs, info = stub_steer._eds_score_population_as_cost(
        samples,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
    )

    torch.testing.assert_close(costs, torch.tensor([-1.0, -3.0, -2.0]))
    torch.testing.assert_close(info["rewards"], torch.tensor([1.0, 3.0, 2.0]))


def test_eds_renoise_reference_uses_scheduler_add_noise(stub_steer):
    population = torch.zeros(2, 64, 128)
    torch.manual_seed(0)
    renoised = stub_steer._eds_renoise_reference(population, 2)

    assert tuple(renoised.shape) == (2, 64, 128)
    assert not torch.equal(renoised, population)


def test_eds_rollout_reference_scores_clean_denoised_population(
    stub_steer,
    stub_adapter,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    cond = stub_steer._rdt_model.encode_inputs(
        torch.zeros(1, 128),
        torch.zeros(1, 128).scatter(1, torch.tensor([[0]]), 1.0),
        [],
        torch.zeros(1, 1, 4),
    )
    cond["action_mask"][0, 0, [39, 40, 41, 42, 43, 44, 10]] = 1.0
    noisy = torch.randn(2, 64, 128)
    score_calls = []

    def fake_score(samples, keypoints, guidance_fns, slice_kind):
        score_calls.append((tuple(samples.shape), slice_kind))
        return torch.tensor([1.0, 2.0], device=samples.device, dtype=samples.dtype)

    monkeypatch.setattr(stub_steer, "_score_particles", fake_score)

    denoised, costs, info = stub_steer._eds_rollout_reference(
        cond=cond,
        action_mask=cond["action_mask"],
        noisy_action=noisy,
        keypoints=torch.zeros(3, 3),
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        n_trunc_steps=2,
    )

    assert tuple(denoised.shape) == (2, 64, 128)
    assert score_calls[-1] == ((2, 64, 128), "eds")
    torch.testing.assert_close(costs, torch.tensor([-1.0, -2.0]))
    torch.testing.assert_close(info["rewards"], torch.tensor([1.0, 2.0]))
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_direct_vls_reward_scoring_converts_to_cost_when_needed \
       tests/test_rdt_steer.py::test_eds_renoise_reference_uses_scheduler_add_noise \
       tests/test_rdt_steer.py::test_eds_rollout_reference_scores_clean_denoised_population -q
```

Expected: fail because EDS helper methods do not exist.

- [ ] **Step 3: Implement scoring and mask helpers**

Add inside `RDTSteer`:

```python
    def _expand_action_mask_for_population(self, action_mask: Tensor, population: Tensor) -> Tensor:
        return action_mask.expand(population.shape[0], population.shape[1], population.shape[2]).to(
            device=population.device,
            dtype=population.dtype,
        )

    def _apply_action_mask(self, actions: Tensor, cond: dict) -> Tensor:
        action_mask = self._expand_action_mask_for_population(cond["action_mask"], actions)
        return actions * action_mask

    def _eds_score_population_as_cost(
        self,
        samples: Tensor,
        *,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
    ) -> tuple[Tensor, dict]:
        rewards = self._score_particles(samples, keypoints, guidance_fns, slice_kind="eds")
        costs = -rewards
        return costs.detach(), {"rewards": rewards.detach()}
```

- [ ] **Step 4: Implement reference-style initial population**

Add:

```python
    def _eds_initial_population(self, *, x_t: Tensor, cond: dict, cfg: _EDSConfig) -> Tensor:
        if cfg.use_initial_cache:
            if cfg.initial_population_cache is None:
                raise ValueError("EDS use_initial_cache=true requires initial_population_cache")
            cache_path = Path(cfg.initial_population_cache)
            cached = torch.load(cache_path, map_location=x_t.device)
            if isinstance(cached, dict) and "initial_population" in cached:
                cached = cached["initial_population"]
            if not torch.is_tensor(cached):
                raise TypeError("Cached EDS initial_population must be a torch.Tensor")
            expected = (cfg.population_size, x_t.shape[1], x_t.shape[2])
            if tuple(cached.shape) != expected:
                raise ValueError(
                    f"Cached EDS initial_population shape {tuple(cached.shape)} != {expected}"
                )
            return cached.to(device=x_t.device, dtype=x_t.dtype)

        population = x_t
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        with torch.no_grad():
            for t in scheduler.timesteps:
                model_output = self._dit(population, t, cond)
                population = scheduler.step(model_output, t, population).prev_sample.to(dtype=x_t.dtype)
        return self._apply_action_mask(population, cond)
```

- [ ] **Step 5: Implement renoise and rollout helpers**

Add:

```python
    def _eds_renoise_reference(self, population_trajectories: Tensor, t: int) -> Tensor:
        scheduler = self._noise_scheduler
        if not hasattr(scheduler, "add_noise"):
            raise RuntimeError("EDS requires a scheduler with add_noise()")
        if not hasattr(scheduler, "timesteps") or len(scheduler.timesteps) == 0:
            scheduler.set_timesteps(self._num_inference_steps)
        t = int(max(1, min(t, len(scheduler.timesteps))))
        noise = torch.randn_like(population_trajectories)
        return scheduler.add_noise(population_trajectories, noise, scheduler.timesteps[-t])

    def _eds_rollout_reference(
        self,
        *,
        cond: dict,
        action_mask: Tensor,
        noisy_action: Tensor,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        n_trunc_steps: int,
    ) -> tuple[Tensor, Tensor, dict]:
        scheduler = self._noise_scheduler
        scheduler.set_timesteps(self._num_inference_steps)
        n_trunc_steps = int(max(1, min(n_trunc_steps, len(scheduler.timesteps))))
        x_t = noisy_action
        mask = self._expand_action_mask_for_population(action_mask, x_t)

        with torch.no_grad():
            for t in scheduler.timesteps[-n_trunc_steps:]:
                model_output = self._dit(x_t, t, cond)
                x_t = scheduler.step(model_output, t, x_t).prev_sample.to(dtype=noisy_action.dtype)

        x_t = x_t * mask
        costs, info = self._eds_score_population_as_cost(
            x_t,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
        )
        return x_t, costs, info
```

- [ ] **Step 6: Run helper tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_direct_vls_reward_scoring_converts_to_cost_when_needed \
       tests/test_rdt_steer.py::test_eds_renoise_reference_uses_scheduler_add_noise \
       tests/test_rdt_steer.py::test_eds_rollout_reference_scores_clean_denoised_population -q
```

Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add EDS population helpers"
```

---

### Task 5: Full EDS Loop, Selection, Metadata, and Visualization

**Files:**
- Modify: `core/rdt_policy_steer.py`
- Modify: `tests/test_rdt_steer.py`
- Test: `tests/test_rdt_steer.py`

- [ ] **Step 1: Add failing full-loop tests**

Append:

```python
def test_eds_loop_uses_cond_once_and_action_population_batch(
    stub_steer,
    stub_adapter,
    mock_batch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 1, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert tuple(action.shape) == (1, 4, 7)
    assert stub_steer._rdt_model.encode_calls == 1
    assert stub_steer._rdt_model.dit.calls
    assert any(latent_shape[0] == 3 for latent_shape, _ in stub_steer._rdt_model.dit.calls)
    assert all(mask_shape[0] == 1 for _, mask_shape in stub_steer._rdt_model.dit.calls)


def test_eds_loop_calls_rollout_after_renoise_each_iteration(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )
    calls = []

    def fake_renoise(population, n_trunc_steps):
        calls.append(("renoise", n_trunc_steps, tuple(population.shape)))
        return population

    def fake_rollout(**kwargs):
        calls.append(("rollout", kwargs["n_trunc_steps"], tuple(kwargs["noisy_action"].shape)))
        noisy = kwargs["noisy_action"]
        costs = torch.arange(noisy.shape[0], device=noisy.device, dtype=noisy.dtype)
        return noisy, costs, {"rewards": -costs}

    monkeypatch.setattr(stub_steer, "_eds_renoise_reference", fake_renoise)
    monkeypatch.setattr(stub_steer, "_eds_rollout_reference", fake_rollout)

    stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 2, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )

    assert calls[0][0] == "renoise"
    assert calls[1][0] == "rollout"
    assert calls[2][0] == "renoise"
    assert calls[3][0] == "rollout"
    assert calls[0][1] == calls[1][1]
    assert calls[2][1] == calls[3][1]


def test_eds_loop_caches_visualization_candidates_best_first(
    stub_steer,
    stub_adapter,
    mock_batch,
    monkeypatch,
):
    stub_steer.post_init(
        adapter=stub_adapter,
        postprocessor=lambda x: x,
        sample_batch_size=2,
        policy_config={"action_chunk_horizon": 4},
    )

    def fake_score(samples, keypoints, guidance_fns, slice_kind):
        return torch.tensor([1.0, 3.0, 2.0], device=samples.device, dtype=samples.dtype)

    monkeypatch.setattr(stub_steer, "_score_particles", fake_score)

    action = stub_steer.select_action(
        mock_batch,
        generate_new_chunk=True,
        use_guidance=True,
        guidance_type="eds",
        eds_config={"population_size": 3, "cem_iters": 1, "temperature": 0.1},
        guidance_fns=[lambda keypoints, traj: traj[..., 0].sum()],
        keypoints=np.zeros((3, 3), dtype=np.float32),
    )
    candidates = stub_steer.get_last_visualization_action_candidates()

    assert tuple(action.shape) == (1, 4, 7)
    assert candidates is not None
    assert tuple(candidates.shape) == (3, 4, 7)
```

- [ ] **Step 2: Run full-loop tests to verify they fail**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_loop_uses_cond_once_and_action_population_batch \
       tests/test_rdt_steer.py::test_eds_loop_calls_rollout_after_renoise_each_iteration \
       tests/test_rdt_steer.py::test_eds_loop_caches_visualization_candidates_best_first -q
```

Expected: fail because `_eds_guided_denoise_loop()` is still a stub.

- [ ] **Step 3: Add EDS ordering and metadata helpers**

Add:

```python
    def _eds_order_candidates_by_cost(self, samples: Tensor, costs: Tensor) -> Tensor:
        if samples.shape[0] <= 1:
            return samples.detach()
        order = torch.argsort(costs.detach())
        return samples.index_select(0, order.to(device=samples.device)).detach()

    def _eds_update_guidance_metadata_from_cost(self, best_cost: Tensor | float, costs: Tensor) -> None:
        if torch.is_tensor(best_cost):
            best_cost_value = float(best_cost.detach().cpu().item())
        else:
            best_cost_value = float(best_cost)
        best_reward = -best_cost_value
        self._last_raw_reward = best_reward
        if self._stage_init_reward is None:
            self._stage_init_reward = best_reward
        self._normalized_reward_from_value(best_reward)
        if torch.is_tensor(costs) and costs.numel() > 0:
            rewards = -costs.detach()
            spread = rewards.max() - rewards.mean()
            self._last_scale = float(torch.clamp(spread, min=0.0).cpu().item())
        else:
            self._last_scale = 0.0
```

- [ ] **Step 4: Replace EDS stub with full loop**

Replace `_eds_guided_denoise_loop()` with:

```python
    def _eds_guided_denoise_loop(
        self,
        *,
        x_t: Tensor,
        cond: dict,
        keypoints: Optional[Tensor],
        guidance_fns: Optional[List[Callable]],
        eds_config: _EDSConfig,
        verbose: bool,
        global_step: int,
        current_stage: int,
    ) -> Tensor:
        cfg = eds_config
        action_mask = cond["action_mask"]

        population = self._eds_initial_population(x_t=x_t, cond=cond, cfg=cfg)
        population = self._apply_action_mask(population, cond)

        population_scores, population_info = self._eds_score_population_as_cost(
            population,
            keypoints=keypoints,
            guidance_fns=guidance_fns,
        )
        population_scores = population_scores.detach()

        trunc_step_schedule = np.linspace(5, 1, cfg.cem_iters).astype(int)

        for i in range(cfg.cem_iters):
            n_trunc_steps = int(trunc_step_schedule[i])
            if cfg.use_cem:
                elites = torch.argsort(population_scores)[: cfg.num_elites]
                indices = torch.randint(
                    0,
                    cfg.num_elites,
                    (cfg.population_size,),
                    device=population.device,
                )
                population = population[elites[indices]]
            else:
                reward_probs = torch.exp(float(cfg.temperature) * -population_scores)
                reward_probs = reward_probs / torch.clamp(reward_probs.sum(), min=1e-8)
                indices = torch.multinomial(
                    reward_probs,
                    cfg.population_size,
                    replacement=True,
                )
                population = population[indices]

            population = self._eds_renoise_reference(population, n_trunc_steps)
            self._reset_scheduler_particle_history_after_resample(self._noise_scheduler)
            population, population_scores, population_info = self._eds_rollout_reference(
                cond=cond,
                action_mask=action_mask,
                noisy_action=population,
                keypoints=keypoints,
                guidance_fns=guidance_fns,
                n_trunc_steps=n_trunc_steps,
            )
            population_scores = population_scores.detach()

        if not torch.isfinite(population).all():
            raise ValueError("EDS-guided RDT latent contains non-finite values")
        if not torch.isfinite(population_scores).all():
            raise ValueError("EDS-guided RDT scores contain non-finite values")

        best_idx = int(torch.argmin(population_scores).item())
        selected = population[best_idx : best_idx + 1]
        self._eds_update_guidance_metadata_from_cost(
            population_scores[best_idx],
            population_scores,
        )
        ordered_candidates = self._eds_order_candidates_by_cost(population, population_scores)
        self._last_visualization_action_candidates = self._decode_visualization_action_candidates(
            ordered_candidates
        )
        return selected
```

- [ ] **Step 5: Run full-loop tests**

Run:

```bash
pytest tests/test_rdt_steer.py::test_eds_loop_uses_cond_once_and_action_population_batch \
       tests/test_rdt_steer.py::test_eds_loop_calls_rollout_after_renoise_each_iteration \
       tests/test_rdt_steer.py::test_eds_loop_caches_visualization_candidates_best_first -q
```

Expected: pass.

- [ ] **Step 6: Run all RDT tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/rdt_policy_steer.py tests/test_rdt_steer.py
git commit -m "feat: add EDS guided denoise loop"
```

---

### Task 6: Final Integration Checks and Evaluation Gate

**Files:**
- Modify: `docs/01_specs/2026-06-06-rdt-eds-guidance-integration-design.md` only if implementation reveals a spec mismatch
- Test: full CPU test suite subset and one optional RDT smoke command

- [ ] **Step 1: Run syntax checks**

Run:

```bash
python -m py_compile main.py core/rdt_policy_steer.py
```

Expected: exit code 0.

- [ ] **Step 2: Run CPU RDT tests**

Run:

```bash
pytest tests/test_rdt_steer.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Check config override parsing**

Run:

```bash
python - <<'PY'
from omegaconf import OmegaConf
base = OmegaConf.load("configs/config.yaml")
override = OmegaConf.from_dotlist([
    "main.use_guidance=true",
    "main.guidance_type=eds",
    "main.eds_config.population_size=4",
    "main.eds_config.cem_iters=2",
])
cfg = OmegaConf.merge(base, override)
assert cfg.main.use_guidance is True
assert cfg.main.guidance_type == "eds"
assert cfg.main.eds_config.population_size == 4
assert cfg.main.eds_config.cem_iters == 2
print("EDS CLI-style overrides ok")
PY
```

Expected: prints `EDS CLI-style overrides ok`.

- [ ] **Step 4: Optional short RDT smoke**

Run only if the local GPU/checkpoint environment is ready:

```bash
python main.py policy.type=rdt main.use_guidance=true main.guidance_type=eds main.eds_config.population_size=2 main.eds_config.cem_iters=1 main.episode_num=1
```

Expected: the program reaches action selection without a shape error in RDT EDS guidance. If the environment stack or GPU is unavailable, record the exact missing dependency or runtime error in the final implementation notes.

- [ ] **Step 5: RDT guided evaluation acceptance gate**

When full evaluation is available, run VLS and EDS under the same checkpoint, suite, tasks, seeds, keypoint tracker, and guidance functions.

Commands should use this structure:

```bash
python main.py policy.type=rdt main.use_guidance=true main.guidance_type=vls
python main.py policy.type=rdt main.use_guidance=true main.guidance_type=eds
```

Report actual values in this format. This example uses a 10-episode run:

```text
VLS SR: 7/10 = 0.70
EDS SR: 6/10 = 0.60
Suite/tasks: libero_object, task ids 0-9
Seeds: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9
EDS config: population_size=16, cem_iters=20, use_cem=false, temperature=0.1
```

Minimum gate: EDS SR is not zero.

Target gate: EDS SR is within 10-15 percentage points of VLS SR on the same evaluation setup, or raw counts show comparable performance on a small run.

- [ ] **Step 6: Commit final validation notes if docs changed**

If implementation changes the spec or adds evaluation notes:

```bash
git add docs/01_specs/2026-06-06-rdt-eds-guidance-integration-design.md
git commit -m "docs: record EDS guidance validation notes"
```

---

## Self-Review Checklist

- Spec requirement: VLS renamed to `_vls_guided_denoise_loop()` -> covered by Task 2.
- Spec requirement: policy-independent config -> covered by Task 1.
- Spec requirement: grouped `vls_config` / `eds_config` select_action inputs -> covered by Tasks 1 and 2.
- Spec requirement: EDS follows reference parameters and core loop -> covered by Tasks 3, 4, and 5.
- Spec requirement: VLS-style `cond once + action population batch + forward expand` -> covered by Task 5 tests.
- Spec requirement: direct VLS reward scoring with cost conversion only when needed -> covered by Task 4.
- Spec requirement: rollout after renoise -> covered by Task 5.
- Spec requirement: final SR acceptance gate -> covered by Task 6.
