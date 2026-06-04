---
archived_on: 2026-06-03
source_worktree: .worktrees/feat/rdt-libero-gt-rollout-integration
source_branch: feat/rdt-libero-gt-rollout-reintegration
source_commit: 360a6d052861
source_path: .worktrees/feat/rdt-libero-gt-rollout-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-05-09-rdt-libero-debug-status-review.md
summary: RDT-LIBERO Debug Status Review
duplicate_sources:
  - .worktrees/feat/rdt-libero-dataset_finetune/docs/docs/02_analysis/rdt_intergration/libero/2026-05-09-rdt-libero-debug-status-review.md
  - .worktrees/feat/rdt-maniskill-ckpt-libero-integration/docs/docs/02_analysis/rdt_intergration/libero/2026-05-09-rdt-libero-debug-status-review.md
---

# RDT-LIBERO Debug Status Review

**Date:** 2026-05-09
**Branch:** `feat/rdt-integration`
**HEAD:** `4bf90b7` (H3 image-flip fix)
**Author intent:** Reconcile original integration plan, failure analyses, and current code with checked-in evidence to decide the next debugging step. No code changes proposed.

---

## 1. Executive Summary

- **H1 (denoising in 8D vs 128D)** is **confirmed fixed** in code and confirmed via numerical comparison against the official RDT inference path (mean abs diff vs official: 0.608 → 0.104).
- **H3 (LIBERO 180° image flip)** is **confirmed fixed in code** (`_undo_libero_flip` flag) and validated only with a synthetic round-trip image check; the live LIBERO run that would prove the SigLIP encoder receives upright frames has not been logged.
- **H2 (zero language embedding)** was always rejected by Round-1 evidence and is rejected by the current code path.
- **Despite H1 and H3 being applied, four separate LIBERO runs after both fixes still show 0/10 success** (`outputs/libero/2026-04-30_06-55-14`, `2026-05-02_11-25-10`, `2026-05-09_09-12-34`, plus the H1-only `2026-04-30_06-34-01`). Step counts max out the timeout (~280 steps/episode) — no early stalls, no crashes. **This is the central unresolved fact.**
- The most likely failure range now sits in three regions that the prior analyses either downgraded or never instrumented end-to-end on a live LIBERO observation:
  1. **Action-conversion regime (`rdt_action_converter.py`)** — saturation + chunk-replay discontinuity.
  2. **Live-observation correctness on LIBERO** — joint-angle proprio, gripper sign and scale, image content actually reaching SigLIP after the flip undo, on a real (not synthetic) frame.
  3. **Domain gap (ManiSkill SAPIEN → LIBERO MuJoCo)** — bounded by what (1) and (2) reveal.
- **The project is NOT ready for another speculative repair round.** A small targeted **evidence-collection round on a live LIBERO observation** (post-H1+H3) is required first. Sections 5–9 specify it.

---

## 2. Source Documents and Code Reviewed

### Plans / specs
- `docs/superpowers/plans/2026-04-22-rdt1b-integration.md` (original integration plan)
- `docs/superpowers/specs/2026-04-22-rdt1b-integration-design.md` (referenced; not re-read for this pass)
- `docs/superpowers/plans/2026-04-30-rdt-debugging-plan.md` (3-phase debugging plan)
- `docs/superpowers/plans/2026-04-30-rdt-repair-plan-v1.md` (H1-only repair plan)

### Failure / status analyses
- `docs/superpowers/analysis/2026-04-30-rdt-libero-failure-analysis.md` (8-section H1–H5 analysis)

### Run logs
- `docs/superpowers/runs/2026-04-30-debugging-plan-session-1.md`
- `docs/superpowers/runs/2026-04-30-phase1-evidence-session-1.md`
- `docs/superpowers/runs/2026-04-30-repair-plan-session-1.md`

### Evidence artifacts
- `docs/superpowers/evidence/round-1/summary.md`
- `docs/superpowers/evidence/round-1/stats/phase2_hypothesis_discrimination.md`
- `docs/superpowers/evidence/round-1/stats/loop_comparison_output.txt` *(working-tree copy is post-H1; git status shows it as modified)*
- `docs/superpowers/evidence/round-1/images/image_check_notes.txt`
- `docs/superpowers/evidence/round-2/summary.md`
- `docs/superpowers/evidence/round-2/step2_loop_comparison_output.txt`
- `docs/superpowers/evidence/round-2/step_h3_loop_comparison_output.txt`
- `docs/superpowers/evidence/round-2/h3_image_check.py` and `h3_orientation_check.png`
- `docs/superpowers/evidence/round-2/rollout_h1_fixed/console_output.txt` (10-episode 0/10 H1-only rollout)
- `docs/superpowers/evidence/round-2/commit_hash.txt` (`7d2380c…`)
- `outputs/libero/{2026-04-30_06-55-14,2026-05-02_11-25-10,2026-05-09_09-12-34}/results.txt` — three additional 0/10 results, all after H1+H3.

### Code (read in full unless noted)
- `core/rdt_policy_steer.py` (full)
- `core/rdt_obs_processor.py` (full)
- `core/rdt_action_converter.py` (full)
- `core/env_adapters/libero_adapter.py` (key sections: `get_policy_observation`, `get_joint_positions`, `get_gripper_state`)
- `main.py` lines 140–195, 555–725 (policy wiring + episode loop)
- `configs/policy.yaml`
- `third_party/rdt/scripts/maniskill_model.py` (`step`, `_format_joint_to_state`, `_unformat_action_to_joint`, `MANISKILL_INDICES`, `DATA_STAT`)
- `third_party/rdt/models/rdt_runner.py` (`conditional_sample`, `predict_action`)
- `third_party/lerobot/.../env_processor.py` `LiberoProcessorStep` (verified through quoted source in evidence; no re-flip elsewhere)

### Git history reviewed
`fddf4ab → 588bec5 → 8c2b591 → eb5ba2f → b02e248 → 894ff06 → … → 7d2380c (H1) → 4bf90b7 (H3)` — the subset that touches RDT files.

---

## 3. Intended Design vs Current Implementation

The original integration plan (2026-04-22) and its on-disk implementation **diverged in five ways during integration**, all of which were either reasoned through or empirically forced. The current code is no longer well-described by the original plan; the design spec file should be considered out of date.

| Layer | Original plan (2026-04-22) | Current implementation | Why it changed |
|---|---|---|---|
| Model wrapping | Plain `RDTSteer` taking `rdt_model` directly; assumes `from_pretrained` exists on the model | `_RDTModelAdapter` wraps the `RoboticDiffusionTransformerModel` plain Python object; `RDTSteer.from_pretrained` calls `create_model()` from `scripts.maniskill_model` and resolves `<repo>/rdt/{config.yaml, mp_rank_00_model_states.pt}` itself. | RDT's `RoboticDiffusionTransformerModel` is not an `nn.Module` and has no `from_pretrained`. Forced by reality. |
| Camera slots | Plan: `[ext_prev, rw_prev, _BLACK_PIL, ext_now, rw_now, _BLACK_PIL]` — black PIL stand-ins. | `[ext_prev, None, None, ext_now, None, None]` — wrist slots are `None` so `maniskill_model.step()` substitutes the SigLIP image-mean background. | Commit `8c2b591`: ManiSkill checkpoint trained with `cam_high` only; black PIL is OOD for SigLIP, the mean-colour background is the in-distribution substitute. |
| Proprio | 14D bimanual (`left_arm zeros`, `right_arm = state[:7]`), state-derived | 8D `[7 Franka joint angles + 1 gripper]` derived directly from the LIBERO adapter via `get_joint_positions()` / `get_gripper_state()`; falls back to `observation.state` only if the adapter accessor fails. | Commit `b02e248`: the LIBERO `observation.state` after `LiberoProcessorStep` is **EEF pose** (`[pos(3), axisangle(3), gripper_qpos(2)]`), not joint angles. Padding into joint slots would feed meter-scale EEF values into rad-scale joint dims. ManiSkill checkpoint requires joint-angle proprio. |
| Action space | "6D delta EEF + gripper" (per the 2026-04-22 spec) | RDT outputs **absolute Franka joint angles** (`MANISKILL_INDICES`); the converter `rdt_chunk_to_libero_actions` denormalizes joints, runs Franka FK, computes incremental EEF deltas, and scales to LIBERO OSC. | Commit `588bec5`: empirical reading of `MANISKILL_INDICES` and `DATA_STAT` confirmed joint-angle output. |
| Denoising loop | 8D noise zero-padded into 128D inside `_RDTDiTAdapter.forward` (initial implementation) | Full 128D Gaussian noise, with `if raw_action_dim == unified_dim: x_unified = x_t` guard; subspace branch retained for stub tests; the post-loop `x_t[:, :, action_indices][:, :, :raw_action_dim]` projects back. | Commit `7d2380c`: the H1 fix. Mean abs diff vs official path 0.608 → 0.104. |
| Image orientation | Plan: no flip handling — assumed images arrive upright. | `_tensor_to_pil` applies `torch.flip(dims=[1,2])` when `_undo_libero_flip` is `True`; flag is set in `RDTSteer.post_init` based on `isinstance(adapter, LiberoAdapter)`. | Commit `4bf90b7`: the H3 fix. `LiberoProcessorStep._process_observation` flips all images 180° for the PI05/diffusion paths; that flip is now reversed before SigLIP encoding. |

**Other notable deviations from plan that are NOT clearly justified anywhere:**

- `_postprocess_actions` always returns particle 0 (`actions[0]`), which is correct only when FKD has resampled "best particle to slot 0". With `use_fkd=False` and `sample_batch_size > 1`, particle 0 is just the first random one and diversity is discarded. The plan and analyses are silent on this.
- `action_chunk_horizon=8` but `pred_horizon=64` (RDT config). Only the first 8 of 64 predicted timesteps are used. With the chunk-replay loop in `main.py:598` (`generate_new_chunk = (action_executed == 0)`, replayed for `action_horizon` steps), this means fresh chunks are re-generated every 8 environment steps. The remaining 56 steps of each prediction are discarded. This is consistent with the plan but the cost has not been profiled.

---

## 4. Root-Cause Status Table

Where rows have multiple sub-causes, the most concrete one is shown. "Code" = directly readable in current source. "Runtime" = present in a checked-in log/output file. "Doc" = asserted in an analysis doc only.

| # | Suspected cause | Where raised | Current code status | Evidence type | Conclusion | Remaining uncertainty |
|---|---|---|---|---|---|---|
| H1 | Denoising loop initialises `x_t` in 8D subspace, zero-pads to 128D | failure-analysis §3.E1; debug plan A2.1 | `rdt_policy_steer.py:708, 911` initialise `x_t` as `(B, 64, unified_action_dim=128)`; `_RDTDiTAdapter.forward:108` passes through unchanged when `raw_action_dim==unified_dim`; final slice extracts `[:, :, action_indices]` | Code + Runtime (loop_comparison: 0.608 → 0.104; joint signs aligned) | **Confirmed fixed** | Mean abs diff is 0.104, missed the <0.10 target by a small margin. Round-2 attributed the residual to H3 — that attribution is no longer testable since the residual was measured pre-H3 and `loop_comparison.py` uses synthetic *black* images that are not affected by orientation. The actual residual cause is **unverified**. |
| H2 | Lang embedding silently falls back to `torch.zeros(1,1,4096)` | failure-analysis §3.D2; debug plan A2.2 | T5 wired in `RDTSteer.post_init:567-579` via `_text_encoder_fn` reusing the real model's T5; cache key uses MD5 hex of the task string consistently in writer (`get_lang_embed:94`) and reader (`:86`); the `except Exception → zeros` fallback exists at `:95-101` but is unreached when T5 is wired. Round-1 measured `norm=16.98`. | Code + Runtime | **Ruled out** for the wired path. | The zero fallback dim (4096) is correct for T5-v1_1-XXL last_hidden_state. If T5 wiring ever fails on a live machine the fallback would silently activate; the `except Exception:` still swallows the cause. Low-priority hardening, not a current cause. |
| H3 | `LiberoProcessorStep._process_observation` flips images 180° before they reach `RDTSteer` | failure-analysis §3.C1; debug plan A2.3 | `rdt_obs_processor.py:118-121` re-flips with `torch.flip(dims=[1,2])` if `_undo_libero_flip=True`. `RDTSteer.post_init:556-558` sets the flag iff adapter is `LiberoAdapter`. Synthetic h3_image_check shows pixel-exact round-trip (diff=0.0). | Code + Synthetic-runtime | **Probably fixed** | No live LIBERO observation has been saved post-H3 to confirm an actual agentview frame arrives upright at SigLIP. The synthetic check only proves the flip composes to identity — not that LIBERO's batch-tensor layout is what the code assumes (`obs[STATIC][0]` is `(C,H,W)`, the flip is on `dims=[1,2]`). |
| H4 | LIBERO OSC scaling constants `_POS_SCALE=0.05`, `_ORI_SCALE=0.5` mis-calibrated | failure-analysis §3.F3; debug plan A2.4 | Unchanged (`rdt_action_converter.py:44-45`). Both Round-1 and Round-2 loop_comparison show **3/24 step-0 position dims saturated at ±1**. | Code (unchanged) + Runtime (saturation) | **Still present** | The Round-2 summary attributes saturation to "H1 wrong joint targets"; that explanation no longer applies post-H1 because joint targets are now aligned. Saturation persists ⇒ the explanation was incomplete OR FK position scale really is too aggressive. **Not re-evaluated on a live LIBERO observation post-H1.** |
| H5 | ManiSkill (SAPIEN) → LIBERO (MuJoCo) zero-shot domain gap | failure-analysis §3.A | Unchanged. | Doc-level only | **Probably present but unverified** | Cannot be evaluated until H4 and live-observation checks are done — until the action stream is plausible, "domain gap" is not testable. |
| New-1 | Chunk-replay discontinuity / horizon mismatch | not raised in prior analyses; identified during this review | `main.py:598` regenerates chunk every `action_horizon=8` env steps. `rdt_action_converter.py` chains FK deltas from `current_joints` (live) → `predicted[0..H-1]` (frozen at chunk start). Action[0] always issues a delta from live joints to predicted[0]; later actions issue deltas between predicted configs. After 8 OSC steps the robot may be far from `predicted[7]`; the next chunk starts a fresh trajectory from wherever it is. | Code | **Probably present, unverified** | Could explain why the robot moves continuously (no early stall after H1) yet never converges. |
| New-2 | Particle 0 selection without FKD | not raised in prior analyses; identified during this review | `rdt_policy_steer.py:733` always returns `actions[0]`. The Round-2 rollout used `use_guidance=False`, so FKD is off — particle 0 is just the first sample. With `sample_batch_size=1` (the diagnostic config) this is moot. | Code | **Latent, not active** in the current rollout config. | Becomes relevant once `use_guidance=True` and `sample_batch_size>1`. |
| New-3 | Gripper sign / scale convention end-to-end | failure-analysis §3.F4 (sign only) | RDT `right_gripper_open`: `+1=open`, `-1=closed` (per RDT convention). `rdt_action_converter.py:166` does `action_gripper = -gripper[i]`. LIBERO/robosuite OSC convention: `-1=open, +1=close`. So RDT positive (open) → LIBERO negative (open). **Net effect: signs match.** Proprio side: `get_gripper_state()` returns sum of two finger qpos (~`[0,0.08]`); `rdt_obs_processor.py:161` divides by 2 → `[0,0.04]`, matching DATA_STAT range. | Code | **Looks correct on paper, unverified end-to-end on a live frame.** | Has not been logged from a real episode. |
| New-4 | Image content arriving at SigLIP not what the model was trained on | failure-analysis §3.C1 indirectly | Even with H3 reversed, the LIBERO `agentview` camera angle/lighting/textures differ substantially from SAPIEN. The ManiSkill checkpoint's image_processor preprocesses with `image_aspect_ratio="pad"` and resize. | Code + Doc | **Probably present** as a degradation, not a bug. | Bounded by H5. |

---

## 5. Confirmed Facts

These are facts that hold simultaneously in **the current code AND a checked-in runtime artifact**.

1. **H1 is fixed in code.** `rdt_policy_steer.py:708` and `:911` allocate `x_t = torch.randn(B, 64, unified_action_dim, …)`. The DiT adapter at `:108` uses the unified tensor verbatim when sizes match. The post-loop projection `x_t[:, :, action_indices][:, :, :raw_action_dim]` is in place at both call sites.
2. **The H1 fix moves the custom path measurably closer to the official path.** Round-1 loop_comparison shows mean abs diff 0.608 (pre-fix) and Round-2 reports 0.104 (post-fix). All seven arm joints now have the same sign as the official `step()` output. Source: `evidence/round-2/summary.md` and `evidence/round-1/summary.md` §3.
3. **H3 is fixed in code.** `rdt_obs_processor.py:118-121` flips the input tensor when `_undo_libero_flip=True`. `rdt_policy_steer.py:557-558` sets the flag iff the adapter is a `LiberoAdapter`. Source: current files.
4. **H3 fix passes a synthetic round-trip image test.** `evidence/round-2/h3_image_check.py` and the embedded text in `step_h3_loop_comparison_output.txt` show pixel-diff 0.0 between original and `_tensor_to_pil` output after a simulated LIBERO flip. Source: `h3_image_check.py:65-69`.
5. **Language embeddings are non-zero on the runtime path.** `text_embed.norm() = 16.98` for "open the top drawer of the cabinet"; two distinct task strings produce embeddings that differ by 7.45 in their first token. Source: `evidence/round-1/stats/loop_comparison_output.txt`. The current code keeps the same wiring (`RDTSteer.post_init` `_enc_fn`).
6. **LIBERO `get_joint_positions()` exists and returns 7 Franka angles in radians.** Verified by `core/env_adapters/libero_adapter.py:916-925` accessing `robot._joint_positions`. The Round-1 evidence used a synthetic Franka home configuration but did not exercise the live adapter.
7. **The robot does NOT early-stall.** All four post-H1 episodes hit the 280-step timeout without `terminated/truncated` triggering early. Source: `evidence/round-2/rollout_h1_fixed/console_output.txt:93-148` and `outputs/libero/.../results.txt`.
8. **No success across 4 separate runs after H1, including 3 runs with H3 fix applied.** `outputs/libero/2026-04-30_06-34-01` (H1 only), `2026-04-30_06-55-14`, `2026-05-02_11-25-10`, `2026-05-09_09-12-34` (all H1+H3): each `results.txt` reports `Success rate: 0.00%` at 0/10. **The H3 fix did not improve success rate.**
9. **H4 saturation is unchanged through both Round-1 and Round-2.** 3 of 24 step-0 position dims saturate at ±1 in both rounds (Round-1 loop_comparison `pos dims saturated (>0.99): 3/24`; Round-2 same).
10. **The official `RoboticDiffusionTransformerModel.step()` produces a temporally smooth joint trajectory** (lag-1 autocorr 0.947). The custom path post-H1 also produces a smooth trajectory (autocorr 0.98). Neither path produces "random noise". This invalidates the original "random motion" framing of the failure.

---

## 6. Remaining High-Probability Causes

Ranked by **(likelihood × independence from already-applied fixes)**.

### #1 — H4 + chunk-replay interaction (Action regime is wrong, not the diffusion regime)

**Why now elevated.** The pre-H1 Round-1 analysis dismissed H4 as a downstream symptom of H1's "wrong joint targets". With H1 fixed, joint targets are correct (joint signs aligned, mean abs diff 0.104) but the saturation pattern persists (3/24 dims at ±1 on step 0) and rollouts still fail. The original explanation no longer holds. Two non-exclusive sub-causes:

- **`_POS_SCALE = 0.05`** assumes a LIBERO OSC where 1 unit ≈ 0.05 m. If the actual gain produces ≈0.01 m/unit, predicted EEF deltas of 5 cm clip to ±1 and the controller actually moves ~1 cm/step.
- **Chunk-replay vs receding-horizon.** `rdt_action_converter.py` chains FK deltas: action[0] = current_live_joints → predicted[0]; action[i>0] = predicted[i-1] → predicted[i]. With OSC saturation, action[0] cannot fully execute in one control step; action[1..7] still issue the same predicted-to-predicted deltas regardless of where the robot actually got. After 8 steps a fresh chunk is regenerated from wherever the robot landed.

**Falsification path:** log raw `delta_pos` (in metres, before `/_POS_SCALE`) for one live LIBERO step. If `|delta_pos|` ≈ 0.05+ at step 0 but actions get clipped, `_POS_SCALE` is too small. If `|delta_pos|` is in the 0.01 m range and step-0 still saturates, the chain or normalization (`_unformat_action_to_joint`) is the issue, not the scale.

### #2 — Live-observation correctness (proprio + image content + gripper) on actual LIBERO frames

All Round-1/Round-2 evidence used **synthetic inputs** (Franka home pose, 384×384 black/coloured images). No checked-in artifact records the **live** values of:

- `proprio_np` returned by `RDTObsProcessor.process` from a LIBERO `get_joint_positions()` call,
- the saved live `images[3]` (post-flip-undo) as it enters `vision_model`,
- `text_embed.norm()` from the real episode-loop call site,
- the raw RDT joint output and the `libero_actions` returned by `rdt_chunk_to_libero_actions` for the same frame.

Until any of these are logged from a real episode, claims that "H1 + H3 are sufficient and only domain gap remains" are unfalsifiable.

**Falsification path:** add 5 one-shot `log.info` lines (first-call-guarded), run one episode, inspect.

### #3 — H3 fix correctness on tensor layout

The H3 fix flips `dims=[1,2]` of a `(C,H,W)` slice. This is correct **iff** `obs["observation.images.image"][0]` is shaped `(C,H,W)` after `LiberoProcessorStep`, i.e. the batch dimension was already consumed by `[0]`. Code reads consistent (`static_t = obs[_STATIC_KEY][0]` then `_tensor_to_pil(static_t)`), but no live frame has been saved to confirm.

**Falsification path:** save `images[3]` (the slot fed into `vision_model`) to disk on the first call of one live episode and inspect.

### #4 — Residual 0.104 mean-abs-diff in loop_comparison

Round-2 attributed this residual to H3 (image flip) — but `loop_comparison.py` uses synthetic *uniform black images* (verified in the round-1 stats output: same `(64,8)` arm output regardless of image content). A 180° flip of black is still black, so H3 cannot be the cause of the 0.104 diff in this comparison. The actual cause is **unknown** and could indicate a remaining mismatch in `encode_inputs` (e.g. a control-frequency value, a dtype subtlety, the `state_adaptor` input shape) that was hidden behind H1's larger 0.608 signal.

**Falsification path:** rerun `loop_comparison.py` on the post-H3 commit (it has not been re-run since H3 was applied — `step_h3_loop_comparison_output.txt` mirrors round-1 numerics). Inspect remaining per-joint differences and trace which conditioning tensor differs.

### #5 — Domain gap (H5)

Genuine but **untestable** until #1–#4 are resolved. Currently a hand-wave.

---

## 7. Causes That Appear Fixed or Unlikely

| Cause | Why it's downgraded |
|---|---|
| H1 (8D vs 128D denoising) | Code change verified; quantitative drop in mean abs diff and joint-sign alignment confirm the fix moves the integration substantially closer to the reference path. |
| H2 (zero language embedding) | Round-1 directly measured non-zero embedding norm; current `_text_encoder_fn` wiring in `RDTSteer.post_init` is unchanged from the working configuration. |
| "Robot motion is fully random" | Loop_comparison (autocorr 0.98) and rollout console output (steady 280 steps/episode, no thrashing pattern) both show smooth, structured behaviour. The *symptom* in the failure-analysis ("random and task-unrelated") was an external interpretation that no longer matches the observed runtime: the motion is **wrong, but not random.** |
| Cache-key mismatch in `load_embedded_tasks` (failure-analysis §3.D1) | The `get_lang_embed` reader uses MD5; the writer at `:94` saves with the same MD5; the `load_embedded_tasks` `pt_file.stem` path is dead in practice (the .pt files in `data/rdt_lang_embeds/` are MD5-named, so stems happen to equal MD5 hashes). |
| Lang embed dimension (4096 fallback vs 512 in plan) | The plan's "1, 1, 512" was an early error in the plan. Current code uses 4096 which matches T5-v1_1-XXL's last_hidden_state. |

---

## 8. Evidence Gaps

Ordered by what would shrink the remaining root-cause range the most.

1. **No live-LIBERO observation has been logged at any point in the integration.** All `loop_comparison`, `image_check`, and `h3_image_check` artifacts use synthetic inputs. The H3 image-content claim, the H4 saturation explanation, and the New-1 chunk-replay claim are all untestable on synthetic data.
2. **No post-H3 rerun of `loop_comparison.py`.** The file `step_h3_loop_comparison_output.txt` is byte-identical in numerics to `step2_loop_comparison_output.txt` (post-H1, pre-H3) — both still print the literal "[H1 TEST] custom loop: x_t = randn(B=1, 64, raw_action_dim=8) … 120 of 128 dims are ZERO" annotation, which is **hard-coded text in `loop_comparison.py`** and does not reflect the actual code path. The numerics happen to match Round-1 because synthetic black images are flip-invariant. **`loop_comparison.py`'s annotated text is misleading and the script has not been kept in sync with the code.**
3. **No `results.txt` is paired with a configuration dump.** Each rollout directory has `main.log` with only HTTP traces — no echo of `policy.type`, `use_guidance`, `sample_batch_size`, `episode_num`, or whether `_undo_libero_flip=True` was actually applied. We are inferring the configuration from commit timestamps and console output.
4. **No comparison of guided vs unguided behaviour post-fix.** All Round-1/Round-2 rollouts use `use_guidance=false`. We cannot distinguish "policy is broken" from "policy is OK but guidance/keypoints are broken".
5. **No raw FK delta in metres** logged from a live frame. The Round-1 `pos dims saturated 3/24` is computed on synthetic black-image conditioning, not on real LIBERO observations, so the absolute saturation rate on a real frame is unknown.
6. **Gripper end-to-end test missing.** The expected behaviour ("gripper opens at task start, closes when grasping") has not been observed or measured in any logged episode.
7. **No video frame from a post-H3 run** saved to evidence/. The `outputs/libero/.../episode_*/episode_*_fail_agentview.mp4` files exist but are not referenced in any analysis doc; nobody has watched them with the hypotheses in mind.

---

## 9. Recommended Next Debugging Steps

These are **diagnostic** steps. **No code logic should change.** Each step adds at most one log statement or one `.save("/tmp/...")` call (first-call-guarded). Run after each step before proceeding.

### Step 1 — Watch one post-H3 episode video

**Uncertainty resolved:** Whether the robot motion has changed character after H3 (e.g. now tries to approach the basket region instead of retreating).
**Where to look:** `outputs/libero/2026-05-09_09-12-34/episode_1/episode_1_fail_agentview.mp4` (or any post-H3 episode).
**Expected falsification patterns:**
- Robot drifts away from the table → image conditioning is still wrong (re-check H3 layout).
- Robot reaches consistently to the **wrong** location independent of task → language conditioning is being ignored even though norm > 0.
- Robot reaches roughly toward the basket but cannot close the gripper → H4 / gripper convention.
- Robot oscillates between two configurations on chunk boundaries → New-1 (chunk-replay).
**Why first:** Free, instant, and immediately re-prioritises later steps. **0 instrumentation required.**

### Step 2 — Log five live values on the first call of one episode

In `RDTSteer.select_action` (after `text_embed = self._obs_processor.get_lang_embed(...)`), guarded by `if not hasattr(self, '_diag_done'): self._diag_done = True`:

- `text_embed.norm()` and `text_embed.shape`
- `proprio.flatten().tolist()` (the live LIBERO joint angles)
- `images[3].save("/tmp/rdt_live_ext_now.png")` (post-flip-undo frame as it enters SigLIP)
- For the unguided path, log the first three timesteps of `raw[0, :3, :]` (RDT normalized output)
- In `rdt_chunk_to_libero_actions`, before return: `print(f"delta_pos={pos_curr-pos_prev}, action_pos={action_pos}, sat={(np.abs(action_pos)>0.99).any()}")` for `i=0`

**Uncertainty resolved:**
- Is text embed real on the live path? (suspected yes; cheap to verify)
- Are proprio joint values in `[-3, 3]` rad and consistent with Franka home? (catches any silent fallback to the EEF-pose path)
- Is the saved frame upright with the table surface at the bottom? (definitive H3 verification)
- Are the raw RDT outputs in plausible normalized range? (catches denormalization or dtype regressions)
- Are FK position deltas around 0.01–0.05 m, or are they 0.5+ m? (calibrates `_POS_SCALE`)

**Why before any code change:** All five values are needed simultaneously to attribute remaining failure. Doing this in one episode (~5 min) cuts the search space dramatically.

### Step 3 — Rerun `loop_comparison.py` on the post-H3 commit and trace residual diff

The script has stale annotations and the numerics in `step_h3_loop_comparison_output.txt` are inherited from a pre-H3 run by virtue of synthetic-input invariance. Either delete the stale `[H1 TEST]` text from `loop_comparison.py` or ignore it; what matters is the numeric `Mean abs diff (official_norm vs custom)`.

If the diff is still 0.10+, instrument both paths to log:
- `cond["state_traj"].shape, .norm(), .float().mean()` (custom path)
- the equivalent `state_traj` produced inside `predict_action` (one-shot patch) for the official path

**Uncertainty resolved:** Whether `encode_inputs` in `_RDTModelAdapter` actually replicates `predict_action`'s pre-loop work bit-for-bit. The 0.104 residual is the smoking gun for any remaining conditioning mismatch.

### Step 4 — Compare `_unformat_action_to_joint` (official) vs the converter's `denormalize_rdt_joints` on the same input

Take one post-H1 chunk, denormalise both ways:
- Official: `real._unformat_action_to_joint(custom_norm_output)` → applies `(x+1)/2 * (action_max - action_min) + action_min` to dims `MANISKILL_INDICES` of a 128D input.
- Custom: `denormalize_rdt_joints` applies the same to the 7 arm dims and clips to URDF limits.

If the values disagree, the action converter's clip-to-URDF or its assumption that the gripper is "already in [-1,1]" is wrong.

**Uncertainty resolved:** Whether `rdt_action_converter.py` is operating on the same numerical scale as the model intends.

### Step 5 — Toggle: feed a synthetic observation with the LIVE proprio but the saved (pre-saved) image, vs the live proprio with a saved upright SAPIEN image

Goal: bisect "image conditioning" vs "everything else". If the robot behaves more reasonably with a known-good SAPIEN frame, the H3 fix is incomplete (maybe colour space, normalisation, or aspect-ratio padding). If behaviour is unchanged, image is not the dominant signal in this regime — the issue is in the action stream.

**Uncertainty resolved:** Whether image conditioning has any task-relevant influence on this checkpoint in the LIBERO domain.

### Step 6 — Decide: chunk-replay vs receding-horizon

Only after Steps 1–5. If Step 1's video shows discontinuities every 8 env steps and Step 2 shows step-0 saturation that smooths within the chunk, set `action_horizon = 1` (in `main.py:565`, via config) so a fresh chunk is generated every env step. Compare success rate on 3 episodes.

**Uncertainty resolved:** Whether the chunk-replay structure is itself a major contributor.

### Step 7 — Only after 1–6 are negative: tune `_POS_SCALE` / `_ORI_SCALE`

Empirical adjustment based on Step 2 and Step 4 evidence. Do NOT do this before, because the values are coupled to the FK chain semantics, which Step 6 may change.

---

## 10. Bottom-Line Assessment

**Repair-readiness: NO. An evidence round must come first.**

Reasoning:
- The two fixes that were committed (H1, H3) **did not measurably improve the user-visible outcome**: success rate is 0/10 in three independent runs after H3, identical to pre-H3.
- The original "0/10 = random motion" framing has been falsified by the loop_comparison data; the motion is smooth and biased toward a specific (wrong) attractor. The remaining failure shape is therefore different from what the failure analysis prioritised.
- All static-only evidence (loop_comparison, h3_image_check) uses synthetic black/coloured images and has decoupled itself from the live LIBERO path. Round-2's confidence assertion that "H1 + H3 are the two confirmed bugs and the rest is domain gap" is no longer warranted.
- Several plausible causes (H4 with unsticking explanation, chunk-replay discontinuity, gripper convention end-to-end, residual 0.104 diff) have **not been falsified on a live observation even once.**

**The smallest move that would genuinely advance the project is Step 1 + Step 2 (Section 9): watch one episode video, then add the five log lines and run one more episode.** Combined cost ≈ 20 minutes and one diagnostic-only commit. Together they will reduce the active hypothesis set from 4–6 to 1–2 and identify which file the next change belongs in.

A repair round started without those two steps will guess at the wrong layer and burn another iteration cycle.
