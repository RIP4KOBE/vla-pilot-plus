# RDT-LIBERO System Map, Semantic Audit, and Live Instrumentation Plan

**Date:** 2026-05-09
**Branch:** `feat/rdt-integration`
**HEAD:** `4bf90b7` (H3 image-flip fix)
**Companion doc:** `2026-05-09-rdt-libero-debug-status-review.md` (status review)

**Purpose:** Reconstruct the system path for `policy.type=rdt` on LIBERO, audit it semantically against the official RDT inference path, and prescribe a minimal, code-preserving instrumentation plan that produces live evidence to discriminate the remaining root-cause candidates.

**Constraints respected throughout:** No control-logic modification, no action-converter modification, no denoising/inference modification, no preprocessing-semantics modification.

---

## A. FACTS

These statements are anchored in the current source or a checked-in artifact. Each cites `file:line` so it can be re-verified.

1. **H1 fix is in place.** Both `_predict_unguided` (`core/rdt_policy_steer.py:708`) and `_guided_denoise_loop` (`:911`) initialise `x_t = torch.randn(B, 64, unified_action_dim, …)`. `_RDTDiTAdapter.forward:108` uses `x_t` directly when `raw_action_dim == unified_dim`. Output is sliced via `x_t[:, :, action_indices][:, :, :raw_action_dim]` (`:719`, `:1002`).
2. **H1 numerical effect was measured.** Round-2 reports mean abs diff vs official `step()` 0.608 → 0.104 and joint-1 sign aligned (`evidence/round-2/summary.md`).
3. **H3 fix is in place.** `core/rdt_obs_processor.py:118-121` calls `torch.flip(img, dims=[1,2])` whenever `_undo_libero_flip=True`. The flag is set in `RDTSteer.post_init` (`core/rdt_policy_steer.py:557-558`) only when adapter is `LiberoAdapter`. Synthetic round-trip pixel diff = 0.0 (`evidence/round-2/h3_image_check.py:65-69`).
4. **Language wiring is non-zero on the live path.** `RDTSteer.post_init:567-579` installs `_text_encoder_fn` that calls `real.encode_instruction`. Round-1 measured `text_embed.norm()=16.98` and a 7.45 first-token diff between two instructions (`evidence/round-1/stats/loop_comparison_output.txt`). The `except Exception → torch.zeros(1,1,4096)` path at `rdt_obs_processor.py:95-101` exists but was not entered in evidence runs.
5. **Observation pipeline order is fixed and known.** `LiberoAdapter.get_policy_observation` (`core/env_adapters/libero_adapter.py:828-857`) reads `self._last_obs` (set in `step()` at `:1439`), runs `self.env_preprocessor` which contains `LiberoProcessorStep` (constructed at `:752-754`), then optionally expands batch dimension. `LiberoProcessorStep._process_observation` applies `torch.flip(img, dims=[2,3])` to all `observation.images.*` keys, and converts `robot_state` to a flat `observation.state` of `[eef_pos(3), eef_axisangle(3), gripper_qpos(2)]`. Source: quoted in `evidence/round-1/images/image_check_notes.txt:7-41`.
6. **Camera mapping.** `agentview_image → observation.images.image`, `robot0_eye_in_hand_image → observation.images.image2` (libero_adapter.py:424-425). RDT discards the wrist (passes `None` so SigLIP substitutes background; verified by current `RDTObsProcessor._build_image_list:67-68`).
7. **Proprio path uses adapter accessors directly, not `observation.state`.** `RDTObsProcessor.process` (`core/rdt_obs_processor.py:155-172`) calls `self._adapter.get_joint_positions()` (returns `robot._joint_positions.copy()`, libero_adapter.py:916-925) and `self._adapter.get_gripper_state()` (sum of two finger qpos, libero_adapter.py:927-942). `observation.state` is only a fallback if the accessor raises.
8. **Action chunk replay cycle is `action_horizon`.** `main.py:565` reads `action_horizon = self.policy._action_chunk_horizon` (= 8 for RDT, from `configs/policy.yaml:34`). `main.py:598` sets `generate_new_chunk = (action_executed == 0)`; `main.py:703` issues `action_chunk[0][action_executed]`; `main.py:705-707` increments and wraps. ⇒ a fresh RDT chunk is denoised every 8 env steps and indexed in order.
9. **Two POS-scale constants disagree by 5×.** The RDT-side converter uses `_POS_SCALE = 0.05` m/unit (`core/rdt_action_converter.py:44`); the LIBERO adapter's trajectory projection used by guidance uses `ACTION_SCALE_POS = 0.01` m/unit (`core/env_adapters/libero_adapter.py:1395`). Both claim to model the same OSC controller; the comment at `:1394` even says "Default OSC position scale is around 0.05 m per unit action" while the constant on the next line is 0.01.
10. **Guidance trajectory projection is dimensionally wrong for RDT.** `RDTSteer._rdt_sample_to_trajectory_3d` (`core/rdt_policy_steer.py:750-757`) slices `sample[0, :H, slice(0,7)]` (RDT joint-angle dims in normalized space) and feeds them to `LiberoAdapter.delta_actions_to_ee_trajectory`, which interprets `[:, :3]` as `(dx, dy, dz)` EEF deltas (libero_adapter.py:1397). RDT does not output EEF deltas — it outputs joint angles. **No rollout exercises this path** because all checked-in runs use `use_guidance=false`.
11. **Gripper sign chain.** RDT predicts `right_gripper_open` ∈ `[-1, 1]` where +1 = open (per `MANISKILL_INDICES`/`DATA_STAT`). Converter negates: `action_gripper = -gripper[i]` (`rdt_action_converter.py:166`). LiberoAdapter then attempts to binarise: `action[-1] = 1 if action[-1] > 0 else -1` (`libero_adapter.py:1432`). The binarisation acts on a torch tensor; the numpy snapshot taken at `:1429` is zero-copy for float32-CPU tensors (RDT output IS float32 CPU per `rdt_policy_steer.py:740-746`), so the mutation propagates to `action_numpy`. Net: LIBERO sees ±1 gripper for RDT.
12. **Round-1's saturation observation.** Synthetic-input loop_comparison shows `grip=0.97` at converter output across step-0..2 (`evidence/round-1/stats/loop_comparison_output.txt`). After negation, LIBERO sees `+0.97 → +1` (close). On a pick task this is "close at step 0", before reaching any object.
13. **Four LIBERO runs report 0/10 success.** `outputs/libero/2026-04-30_06-34-01/results.txt` (post-H1 only), `2026-04-30_06-55-14`, `2026-05-02_11-25-10`, `2026-05-09_09-12-34` (all post-H1+H3). The first runs to 280 steps/episode without early termination (`evidence/round-2/rollout_h1_fixed/console_output.txt:93-148`).
14. **`loop_comparison.py` evidence files are stale.** `evidence/round-2/step_h3_loop_comparison_output.txt` is byte-identical in numerics to the post-H1 output and still prints the literal `[H1 TEST] … 120 of 128 dims are ZERO` annotation. Synthetic black images are flip-invariant, so the script cannot exercise H3 — but its annotated text suggests H1 is also unfixed, which is wrong.

---

## B. SYSTEM MAP

### B.1 Live runtime path for `policy.type=rdt` on LIBERO

```
                                    LIBERO env
                              (robosuite + MuJoCo)
                                       │ raw_obs dict
                                       │  ├── agentview_image     (H,W,3) uint8
                                       │  ├── robot0_eye_in_hand_image (H,W,3)
                                       │  └── robot_state {eef.{pos,quat}, gripper.qpos}
                                       ▼
        LIBERO-PRO env step() (third_party/libero_pro)
                                       │ flattens to {observation.images.image,
                                       │  observation.images.image2,
                                       │  observation.robot_state}
                                       ▼
            LiberoAdapter.step() ──────┐  cache as self._last_obs
                  (libero_adapter.py:1421-1439)
                                       │
                                       ▼
       Main loop calls self._get_policy_observation()                     main.py:709
                                       │
                                       ▼
       LiberoAdapter.get_policy_observation()                  libero_adapter.py:828
                                       │ obs = self._last_obs.copy()
                                       │ obs["task"] = [task_desc] * sample_num
                                       ▼
       env_preprocessor (PolicyProcessorPipeline)              libero_adapter.py:752
         └── LiberoProcessorStep._process_observation
              ├── torch.flip(img, dims=[2,3])  ← 180° rotation        ← H3 source
              └── robot_state → observation.state =
                       [eef_pos(3), eef_axisangle(3), gripper_qpos(2)]
                                       │
                                       ▼  obs dict (B,C,H,W) tensors
        main.py:626   self.policy.select_action(obs, generate_new_chunk=…)
                                       │
                                       ▼
   ┌───────────────  RDTSteer.select_action ────────────────┐         core/rdt_policy_steer.py:622
   │                                                         │
   │  if generate_new_chunk:                                  │
   │     RDTObsProcessor.process(obs)        ──────────────┐ │
   │     RDTObsProcessor.get_lang_embed(task_str, device) ─┼─┼─→ T5 via _text_encoder_fn
   │     if use_guidance: _guided_denoise_loop             │ │   (real.encode_instruction)
   │     else:           _predict_unguided                 │ │
   │                                                         │
   └───────────────────────────────────────────────────────┘
                                       │
   ┌───  RDTObsProcessor.process ───┐  │                              core/rdt_obs_processor.py:123
   │ static_t = obs["…image"][0]   │  │
   │ if _undo_libero_flip:         │  │   ← H3 fix
   │   torch.flip(static_t, [1,2]) │  │
   │ ext_now = PIL @384            │  │
   │ images = [ext_prev, None,None,│  │
   │           ext_now,  None,None]│  │
   │ proprio_np[:7] = adapter.     │  │
   │   get_joint_positions()[:7]   │  │
   │ proprio_np[7]  = adapter.     │  │
   │   get_gripper_state()/2       │  │
   └───────────────────────────────┘  │
                                       │ images, proprio (1,8), task_str
                                       ▼
       _RDTModelAdapter.encode_inputs(proprio, images, text_embed)   core/rdt_policy_steer.py:198
         ├── vision_model(SigLIP) → image_embeds
         ├── _format_joint_to_state → states (1,1,128), state_elem_mask (1,128)
         │                            with MANISKILL_INDICES=[0..6, 10]
         ├── state_tokens = cat([states, state_elem_mask.unsqueeze(1)], dim=2)
         └── policy.adapt_conditions → cond{lang_cond, img_cond, state_traj,
                                             action_mask, action_indices,
                                             unified_action_dim=128}
                                       │
                                       ▼ (custom denoising loop — branches from official)
        x_t = randn(B, 64, 128)        ← H1 fix
        for t in scheduler.timesteps:
          noise_pred = _RDTDiTAdapter.forward(x_t, t, cond)           core/rdt_policy_steer.py:66-135
                       │
                       │ identity inflate (raw==unified=128)
                       │ action_traj = cat([x_unified, action_mask_full], dim=2)
                       │ state_action_traj = cat([state_traj, action_traj], dim=1)
                       │ runner.model(...)  ← real RDT DiT
                       └────────────────────────
          x_t = scheduler.step(noise_pred, t, x_t).prev_sample
          # if guided: RBF diversity / keypoint gradient / FKD here (currently broken — see Fact 10)
                                       │
                                       ▼
        return x_t[:, :, action_indices][:, :, :8]     # (B, 64, 8) normalized in [-1,1]
                                       │
                                       ▼
       _postprocess_actions                                            core/rdt_policy_steer.py:723
         best = actions[0]                                # particle 0 (FKD-best slot or first)
         chunk_np = best[:H].cpu().numpy()                # (8, 8)
         current_joints = adapter.get_joint_positions()   # live
         libero_chunk = rdt_chunk_to_libero_actions(chunk_np, current_joints)
                                       │
                                       ▼  (1, 8, 7) torch.float32 CPU
   ┌───  rdt_chunk_to_libero_actions  ───┐                            core/rdt_action_converter.py
   │ for i in 0..H:                       │
   │   q = denormalize(arm_norm[i])  +    │
   │       clip to FRANKA_Q_MIN/MAX       │
   │   pos_curr,rot_curr = franka_fk(q)   │
   │   delta_pos = pos_curr - pos_prev    │
   │   delta_axisangle = rot_to_aa(...)   │
   │   action_pos = clip(d_pos/0.05, ±1)  │  ← _POS_SCALE
   │   action_ori = clip(d_aa /0.5,  ±1)  │  ← _ORI_SCALE
   │   action_gripper = -gripper_norm[i]  │
   └─────────────────────────────────────┘
                                       │
                                       ▼
       main.py:703  self.adapter.step(action_chunk[0][action_executed])    # (7,)
                                       │
                                       ▼
       LiberoAdapter.step                                            libero_adapter.py:1421
         action_numpy = action.float().to("cpu").numpy()  # zero-copy view
         action[-1] = 1 if action[-1]>0 else -1            # binarise gripper
         current_env.step(action_numpy)                    # LIBERO-PRO step
                                       │
                                       ▼
        LIBERO-PRO env (OSC controller) → MuJoCo physics → next obs
                                       │
                                       └── back to top
```

### B.2 Two key branching points vs the official path

| Branch point | Official `RoboticDiffusionTransformerModel.step()` | Custom path |
|---|---|---|
| Pre-loop conditioning | `predict_action`: `state_tokens=cat([state,action_mask],-1)` → `adapt_conditions` (`rdt_runner.py:237-239`) | `_RDTModelAdapter.encode_inputs`: identical structure (`rdt_policy_steer.py:273-276`) |
| Inner loop | `conditional_sample`: `x_t=randn(B,64,128)`; loop body = `cat([x_t,action_mask],-1) → state_adaptor → cat with state_traj → model(...)` (`rdt_runner.py:135-156`); apply mask at end (`:160`) | `_predict_unguided` / `_guided_denoise_loop`: `x_t=randn(B,64,128)`; `_RDTDiTAdapter.forward` replicates inner body; mask applied implicitly by post-loop slicing of `action_indices` |
| Post-loop | `_unformat_action_to_joint`: slice `MANISKILL_INDICES`, denormalize via `(x+1)/2*(action_max-action_min)+action_min` (`maniskill_model.py:187-195`) | RDTSteer returns NORMALIZED `(B,64,8)`; denormalization deferred to `denormalize_rdt_joints` inside the converter (only for arm dims) |

---

## C. SEMANTIC AUDIT TABLE

| Item | Official / training path | Current integration path | Evidence | Status |
|---|---|---|---|---|
| **Static-camera content** | ManiSkill `cam_high`, upright SAPIEN render @ 384×384, padded to square via image_mean | LIBERO `agentview_image`, MuJoCo render → `LiberoProcessorStep` 180° flip → undone in `RDTObsProcessor._tensor_to_pil` → resize 384×384 → padded square via image_mean | rdt_obs_processor.py:118-121, 149; libero_adapter.py:391-425; image_check_notes.txt | **MATCH (orientation), UNKNOWN (content)** — synthetic round-trip OK; live frame never saved post-H3 |
| **Wrist-camera content** | empty / SigLIP image-mean background | `None` → `maniskill_model.step` substitutes image-mean background | rdt_obs_processor.py:67-68; maniskill_model.py:221-223 | **MATCH** |
| **Image preprocessing** | `image_processor.preprocess` from SigLIP-so400m-patch14-384, pad to square (`image_aspect_ratio=pad`) | `_RDTModelAdapter.encode_inputs:228-254` replicates it (Resize + expand2square + image_processor.preprocess) | rdt_policy_steer.py:228-254 vs maniskill_model.py:219-251 | **MATCH** |
| **Image normalization range** | Float in image_processor's expected range (it normalises internally) | Same path | rdt_policy_steer.py:248-254 | **MATCH** |
| **Proprio semantics** | 8D = 7 Franka joint angles in rad + 1 gripper qpos in [0, 0.04]; passed as `(1, 1, 8)` and broadcast into MANISKILL_INDICES of 128D state | 8D from `adapter.get_joint_positions()[:7]` (rad) + `adapter.get_gripper_state()/2` (~[0, 0.04]) | rdt_obs_processor.py:155-164; libero_adapter.py:916-942 | **MATCH on paper, UNKNOWN live** — live values never logged |
| **Proprio normalization** | `_format_joint_to_state` does `(joints-state_min)/(state_max-state_min)*2-1` then scatters into 128D | Same — calls `real._format_joint_to_state` | rdt_policy_steer.py:260 | **MATCH** |
| **Language token embed** | T5-v1_1-XXL last_hidden_state (1, ≤K, 4096), bf16 | Same: `real.encode_instruction(instr, device=real.device)` then `.float().cpu()` | rdt_policy_steer.py:567-577; round-1 norm=16.98 | **MATCH** |
| **Language conditioning into DiT** | `predict_action(lang_tokens=text_embeds, lang_attn_mask=ones)` → `adapt_conditions` | `_RDTModelAdapter.encode_inputs`: same call structure | rdt_policy_steer.py:267-276 | **MATCH** |
| **Action latent dim during denoising** | 128D Gaussian noise throughout loop; mask applied at `:160` | 128D Gaussian noise; mask = post-loop slice of `action_indices` | rdt_policy_steer.py:708, 911; rdt_runner.py:135-160 | **MATCH** |
| **Action denormalization** | `_unformat_action_to_joint` denorms ALL 8 dims (incl gripper) via `(x+1)/2*(action_max-action_min)+action_min` | `denormalize_rdt_joints` denorms 7 arm dims with same constants and clips to FRANKA_Q_MIN/MAX; gripper passed through as `[-1,1]` | maniskill_model.py:187-195 vs rdt_action_converter.py:93-107 | **MATCH (gripper denorm is identity since action_min=-1, action_max=+1)** |
| **Output action semantics in train space** | Absolute Franka joint angles (rad) per chunk step | Same — converter denormalises to absolute angles | rdt_action_converter.py:144-147 | **MATCH** |
| **LIBERO action semantics** | N/A (not the training env) | OSC delta `[dx, dy, dz, drx, dry, drz, gripper]` ∈ [-1, 1]; computed via Franka FK on consecutive predicted configs | rdt_action_converter.py:110-170 | **DIFFERENT BY DESIGN** — bridge layer; correctness depends on POS/ORI scale |
| **Gripper sign convention** | RDT `right_gripper_open`: +1=open | Converter: `-gripper[i]`; LIBERO: -1=open, +1=close; LiberoAdapter binarises | rdt_action_converter.py:164-166; libero_adapter.py:1432 | **MATCH on paper, UNKNOWN live** — never observed gripper open/close at the right moment in any logged episode |
| **POS scale (m per LIBERO unit)** | LIBERO OSC controller gain (unspecified in repo) | Converter: 0.05 m/unit; trajectory-projection helper: 0.01 m/unit | rdt_action_converter.py:44 vs libero_adapter.py:1395 | **MISMATCH between two internal users** — at least one is wrong |
| **Action chunk replay** | RDT was trained at `pred_horizon=64` chunked replay (control_frequency=25, RDT issues 64-step chunks) | `action_horizon=8`; chunk regenerated every 8 env steps; predicted steps 8..63 discarded; FK chains use frozen `current_joints` from chunk-start time | configs/policy.yaml:34; main.py:565,598,705-707; rdt_action_converter.py:144 | **MISMATCH** — receding-horizon vs chunk-replay gap not analysed in any prior doc |
| **Particle aggregation** | N/A (single particle in official inference) | Always returns particle 0; correct only when FKD has resampled best→0; with `use_guidance=False` and `sample_batch_size>1` this discards diversity | rdt_policy_steer.py:733 | **MISMATCH (latent)** — not active in current rollouts (sample_batch_size=1) |
| **Guidance trajectory projection** | N/A | Slices `sample[0, :H, 0:7]` (RDT joint-angle dims) and feeds to `delta_actions_to_ee_trajectory` which assumes input is `[dx,dy,dz,…]` EEF delta | rdt_policy_steer.py:750-757 vs libero_adapter.py:1359-1397 | **MISMATCH** — semantically wrong; not exercised because rollouts use `use_guidance=False` |

---

## D. PRIORITIZED HYPOTHESES

Strict separation between **FACT-supported** suspicions (an evidence artifact in the repo points at this) and **HYPOTHESIS** (plausible from code reading but not yet observed).

### D.1 FACT-supported suspicions

1. **F-1 — POS-scale inconsistency between converter and trajectory helper.**
   Direct fact: `core/rdt_action_converter.py:44` says 0.05 m/unit, `core/env_adapters/libero_adapter.py:1395` says 0.01 m/unit, both purport to model the same OSC. The 5× factor is a fact in the source. Whether it changes rollout outcome is a separate hypothesis. Even if `delta_actions_to_ee_trajectory` is unused at inference time today (it is, when `use_guidance=False`), the inconsistency means at least one of the two sites is wrong, and `_POS_SCALE=0.05` is the one that affects the action stream.

2. **F-2 — Step-0 saturation persists post-H1.**
   `evidence/round-2/step2_loop_comparison_output.txt` shows 3/24 step-0 position dims at ±1.0 even after H1. Round-2's explanation ("downstream of H1 wrong joint targets") no longer applies because joint signs are now aligned with the official path. Saturation persists ⇒ explanation is incomplete; F-1 (or the chunk-replay structure) is the next candidate.

3. **F-3 — H3 was committed without a live validation.**
   `evidence/round-2/h3_image_check.py` validates only a synthetic round-trip (pixel diff = 0.0). No live LIBERO frame post-H3 is in `evidence/`. The four post-H3 `outputs/libero/.../results.txt` are 0/10, identical to post-H1 only. The fact that the fix is committed does not entail it works on the live tensor layout.

4. **F-4 — Guidance/FKD path is broken by design for RDT.**
   `_rdt_sample_to_trajectory_3d` feeds joint-space samples to a function that interprets them as EEF deltas. Source-readable mismatch in `rdt_policy_steer.py:750-757` vs `libero_adapter.py:1397`. Not contributing to current 0/10 (rollouts use `use_guidance=False`), but blocks the entire VLS steering goal of the project.

5. **F-5 — `loop_comparison.py` has stale annotations and is no longer a reliable test.**
   `evidence/round-2/step_h3_loop_comparison_output.txt` is byte-identical to the post-H1 output and prints text suggesting H1 is unfixed. Synthetic black-image inputs are flip-invariant, so the script can never detect H3 effects. Any future "H3 verified by loop_comparison" claim would be unfounded.

### D.2 Hypotheses (code-readable but unobserved on a live LIBERO frame)

1. **H-A — `_POS_SCALE = 0.05` is too large, causing FK position deltas to clip.**
   Plausible because Round-1 saw saturation. Falsified by logging raw `delta_pos` (in metres) and comparing to a measured/tested OSC gain.

2. **H-B — Chunk-replay discontinuity dominates.**
   With `action_horizon=8` and step-0 saturation, the robot likely cannot reach `predicted[0]` in one OSC step. Chunked replay then issues `predicted[i-1]→predicted[i]` deltas that depend on a configuration the robot never reached. After 8 steps a fresh chunk starts from wherever the robot is, breaking the FK chain assumption. Falsified by toggling `action_horizon=1` once Step 1 of the diagnostic plan motivates it.

3. **H-C — Live joint-angle proprio differs from the synthetic Franka home used in evidence.**
   `get_joint_positions()` returns `robot._joint_positions.copy()` — but no live value has been logged. If LIBERO's `_joint_positions` is shorter than 7 (joint-only, no gripper), or returns some unexpected order, downstream is wrong silently.

4. **H-D — Live image content (post-flip-undo) differs from the synthetic check in unintended ways** (e.g. colour-channel order, normalisation range, padding background colour). Synthetic check used a uniform 2-colour image, not a MuJoCo render.

5. **H-E — Residual 0.104 mean abs diff vs official path is a real mismatch in `encode_inputs`** (e.g. `state_adaptor` input shape, `ctrl_freqs` propagation, dtype handling) hidden behind the larger H1 signal pre-fix.

6. **H-F — Gripper continuous-vs-binary effect.** Round-1 synthetic-input data shows converter gripper ≈ 0.97 at step 0; LIBERO binarises to +1 (close) at episode start, before reaching any object. Could explain 0% pick success for `libero_object`. Not yet measured on a live frame.

7. **H-G — Domain gap (H5 from old analyses).** Genuinely possible; not a current candidate to invest in until F-1, H-A..H-F are resolved.

---

## E. MINIMAL INSTRUMENTATION PLAN

**Constraints respected:** no logic changes; only `log.info`, `print`, and one-shot `.save("/tmp/...")` guarded by `not hasattr(self, '_diag_done')`. Each location records the minimum needed to discriminate one or more hypotheses.

### E.1 Locations and exact fields

| # | File:Line | Insertion point | Fields to record (one-shot only) | Hypotheses validated |
|---|---|---|---|---|
| L1 | `core/rdt_policy_steer.py:644` | inside `select_action`, immediately after `text_embed = self._obs_processor.get_lang_embed(task_str, self.device)` | `text_embed.shape`, `text_embed.norm().item()`, `text_embed.abs().max().item()`, `task_str` | H2 still ruled out on live path (vs synthetic) |
| L2 | `core/rdt_obs_processor.py:175` | inside `process`, after `proprio_np` is fully populated and before `torch.from_numpy` | `proprio_np.tolist()`, source flag (`self._adapter is not None and hasattr(...,"get_joint_positions")`), `self._undo_libero_flip` | H-C, also verifies adapter joint path is active (not `obs.state` fallback) |
| L3 | `core/rdt_obs_processor.py:149` | after `images = self._build_image_list(...)` | one-shot `images[3].save("/tmp/rdt_live_ext_now.png")`, `images[0].save("/tmp/rdt_live_ext_prev.png")`, plus log of `static_t.shape, static_t.dtype, static_t.min().item(), static_t.max().item()` BEFORE flip-undo | F-3, H-D |
| L4 | `core/rdt_policy_steer.py:719` | end of `_predict_unguided`, just before return | `x_t.shape`, `x_t.abs().max().item()`, per-arm-dim mean of the first 3 timesteps after slice (`out[0, :3, :7].mean(0).tolist()`), `out[0, :3, 7].tolist()` (gripper dim) | H-E (compares with official trajectory shapes); H-F (gripper trace) |
| L5 | `core/rdt_action_converter.py:168` | end of `rdt_chunk_to_libero_actions`, before return; one-shot guard via a module-level `_diag_done` | for `i in range(min(H, 3))`: `delta_pos.tolist()` (metres), `delta_axisangle.tolist()` (rad), `action_pos` pre-clip (`delta_pos / _POS_SCALE`), `action_pos` post-clip, `action_gripper`, `q_curr` (denormalized), `q_prev` (current_joints if i==0) | F-1, F-2, H-A |
| L6 | `core/env_adapters/libero_adapter.py:1432` | inside `step`, just before `current_env.step(action_numpy)` | one-shot: `action_numpy.tolist()`, episode_step, `self.episode_step` | F-2 (validates LIBERO sees what the converter produced post-binarisation), H-F |
| L7 | `core/rdt_policy_steer.py:189` | end of `_init_policy` block (or end of `Main.__init__` stage), one-shot | `cfg.policy`, `cfg.main.use_guidance`, `cfg.main.sample_batch_size`, `cfg.main.episode_num`, commit hash from `git rev-parse HEAD`, list of `outputs/.../episode_1` directory contents at end of run | F-3 (rollout repro context); also fills the gap that current `main.log` lacks config |

### E.2 Capture protocol

1. Apply L1–L7 in a single diagnostic-only commit. **No other code change.**
2. Set `main.episode_num=1`, `main.use_guidance=false`, `main.sample_batch_size=1`, `backend.libero.suite_name=libero_object`, `backend.libero.task_id=0` (matches the failing reference).
3. Run one episode. Save `console_output.txt`, copy `/tmp/rdt_live_ext_*.png` into `evidence/round-3/`, copy `outputs/libero/<latest>/episode_1/episode_1_fail_agentview.mp4`.
4. Revert the diagnostic commit (`git revert HEAD`) before any subsequent fix attempt so the codebase is clean for a single-fix repair iteration.

### E.3 Decision rules

- **L1 norm < 1.0** → live language path is broken (would contradict Round-1's synthetic norm); urgent.
- **L2 source flag = `obs.state` fallback** OR **L2 first 7 values not in [-3.0, 3.0]** → H-C confirmed; investigate `get_joint_positions`.
- **L3 saved frame upside-down** OR **table not at the bottom half** → H3 fix is wrong on live tensor layout; revisit.
- **L4 gripper dim > 0** at step 0 of a pick episode → H-F confirmed; gripper closes prematurely.
- **L5 `delta_pos` magnitudes ≪ 0.05 m AND post-clip `action_pos` is at ±1** → F-1 confirmed: `_POS_SCALE` is too large and is the dominant contributor.
- **L5 `delta_pos` magnitudes ≫ 0.05 m** → either denormalization is wrong (H-E) OR FK is producing non-physical configurations (clip-to-FRANKA range mismatch).
- **L6 `action_numpy[-1]` not in {-1, +1}** → binarisation is silently broken on a real path (could happen if RDT's chunk is later in chained ops).
- **All L1–L6 plausible AND L3 frame is upright AND no scale issues** → primary cause is H-B (chunk replay) or H-G (domain gap); proceed to a chunk-horizon=1 toggle as the next experiment.

---

## F. RISKS / UNKNOWNs

1. **Repo evidence drift.** `evidence/round-1/stats/loop_comparison_output.txt` has been silently overwritten (working tree shows it as `M` in git) and `step_h3_loop_comparison_output.txt` was created for an H3 fix that the script cannot detect. Future evidence rounds should either restamp or place new files in `evidence/round-N/` without overwriting earlier rounds.
2. **`main.log` does not capture configuration.** Hydra's logging here only catches httpx traces; nothing is recorded about `use_guidance`, `sample_batch_size`, or `policy.type`. Without L7 above, post-hoc reconstruction of past runs is unreliable.
3. **All static evidence used synthetic Franka home pose + black images.** This means F-3 and several MATCH/MATCH-on-paper rows in §C are formally untested on live data. The audit is, by definition, contingent on L1–L6 producing plausible values.
4. **Gripper binarisation mutation correctness depends on torch dtype and device of `action_chunk`.** For RDT today (float32 CPU) the mutation propagates to `action_numpy` via shared memory. If a future change moves RDT output to bfloat16 or GPU, the binarisation would silently become a no-op without triggering a test. This is a fragility, not a current bug.
5. **`_POS_SCALE`/`_ORI_SCALE` calibration source is unstated.** The converter comment claims "kp ≈ 150, action_scale ≈ 0.05" but does not cite a LIBERO version, suite, or controller-config file. The trajectory-helper constant 0.01 has no citation either. Either constant could be a stale guess.
6. **`action_horizon=8` vs `pred_horizon=64`.** RDT's `pred_horizon=64` is fixed by the checkpoint. Discarding 56 of 64 predicted steps every chunk is a lot; the cost has not been benchmarked.
7. **Chunk regenerated with live `current_joints` but `predicted[0..7]` sampled with stale proprio.** Inside `rdt_chunk_to_libero_actions`, `q_sequence[0] = current_joints` is the live joint state at the moment of chunk-end execution, while predictions were sampled at chunk-start. Subtle drift between sampling time and execution time is not analysed anywhere.
8. **No CALVIN evidence in this branch.** The original integration plan included CALVIN smoke runs (Task 8). They have not been re-run after H1/H3. If `_undo_libero_flip` accidentally triggers for CALVIN (it shouldn't, but only the `isinstance` check guards it), CALVIN images would be flipped wrongly. Worth a one-line check before any future CALVIN run.
9. **Guidance path is broken (Fact 10 / F-4).** Even if all the above are fixed, `use_guidance=true` for RDT will produce nonsense gradients because `delta_actions_to_ee_trajectory` is fed joint-space inputs. This is **not on the critical path for fixing 0/10 unguided rollouts** but must be resolved before steering experiments can run.
10. **Domain-gap floor.** Even with all integration bugs resolved, ManiSkill (SAPIEN, pick-and-place pretraining) → LIBERO (MuJoCo, libero_object) is a large zero-shot transfer. The success-rate ceiling under a perfect integration is unknown. This audit cannot estimate it.
