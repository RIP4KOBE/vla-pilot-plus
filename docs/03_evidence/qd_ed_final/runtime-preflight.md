# Runtime / input preflight — 2026-09-21

This diagnostic node performed CPU reads, local dependency exports, owned runtime setup, and an opt-in cache identity repair. No GPU allocation, CUDA initialization, EGL display/context initialization, simulator rollout, API request, package installation, training, or old-artifact mutation was performed. A later parent-authorized metadata-only EGL device enumeration is recorded below. `torch.cuda.is_initialized()` remained false in the guarded CPU import and init-state audit. Root authorized the bounded repairs after the initial read-only audit.

## Result and remaining dispatch blockers

Runtime files are prepared and fingerprinted. Online evaluation is **not admitted**:

1. Physical GPU7 is externally occupied according to the root admission check. This node did not initialize CUDA or an EGL display/context. Do not share/preempt external processes; only one worker is allowed.
2. Metadata-only enumeration now verifies physical CUDA GPU7 → EGL device4 on driver580.65.06. Rendering/CUDA validation remains unperformed. Set `CUDA_DEVICE_ORDER=PCI_BUS_ID`, resolve the actual CUDA ordinal/UUID/PCI identity and EGL device's CUDA association after exclusive GPU7 admission, and bind both. Do not silently use EGL0 or trust the historical table.
3. Frozen Stage provider is `https://api.poe.com/v1`, model `gemini-2.5-flash`. The currently injected provider hostname is different (root inspected hostname only). `OPENAI_API_KEY` exists; `GOOGLE_API_KEY` does not. Presence does not establish provider compatibility. `provider_ready=false`: root awaits the user's provider decision. Never redirect an existing key to a different endpoint, write it into argv/Hydra/manifests, or recover it from logs.
4. The opt-in runtime identity gate has been verified on CPU but cannot establish live simulator keypoint identity before an admitted episode. It fails closed if task ID differs, keypoint0 is not the actual task target, or no basket keypoint is present. It does not reorder points or add perception retries.

## Owned artifacts and identities

- Machine-readable audit: `data/runtime-inventory.json`. It records full content SHA-256 for Object EMA, T5, SigLIP, DINOv2, all 10 BDDL/init files, and row0 of each init tensor, plus package metadata and initial/final blockers.
- Runtime setup manifest: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/setup_manifest.json` (`qd-ed-runtime-setup-v1`, 3287 content-hashed files). Each `files` entry has absolute `path`, `size_bytes`, and `sha256`; `tasks["0".."9"]` binds task cache, BDDL, init file, target/basket identity, and init index0. Runner must validate these identities before dispatch.
- Preparation script: `scripts/qd_ed_runtime_setup.py`; tests: `tests/test_qd_ed_runtime_setup.py`.
- Object EMA SHA-256: `b4e3631db326689297cd2f0b02d32ade9dc6ee9ae09c03171add64b80e86aaa1`.
- T5 snapshot: `3db67ab1af984cf10548a73467f0e5bca2aaaeb2`; full weights hash `c8407a9ae21075667be98f84f4c93e8a7bfc772a352cd2e6998f5916f7181db8`.
- SigLIP snapshot: `9fdffc58afc957d1a03a25b10dba0329ab15c2a3`; full weights hash `ea2abad2b7f8a9c1aa5e49a244d5d57ffa71c56f720c94bc5d240ef4d6e1d94a`.
- DINOv2 ViT-B/14 weights hash: `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73`.

## Dependencies and path repair

Fresh source gitlink directories `third_party/rdt`, `third_party/lerobot`, and `third_party/calvin` were empty. The active environment's LeRobot originally resolved into an old worktree, risking hidden dependency drift. The new RDT and LeRobot directories now contain clean local `git archive` exports of the exact pinned gitlink commits (`b896f4dcac8ed1c3fae4a056200db267607f131f`, `715debf6c1723a28f1a57d4274a8c4ec35b6a417`) without `.git` metadata. No remote fetch or installation was needed. CALVIN remains unused for the LIBERO/RDT path; SAM3 is disabled and does not require installation.

The inherited `.libero_config/config.yaml` points into the old autoresearch worktree. It remains unused by the new runtime contract: `LIBERO_CONFIG_PATH` points at the owned runtime config, with copies of the 10 swap BDDLs and 10 init files. Assets and benchmark source resolve into the new worktree and are hashed in the runtime manifest. No stale-path fallback is needed. The DINO hub repository, trusted list, and exact local weights are copied to the owned runtime `torch/hub` cache. Offline HF flags prevent downloads. Old runners' cache/output paths under legacy locations are not reused for mutation or resume.

The `vla-pilot` interpreter is `/home/hynx/miniconda3/envs/vla-pilot/bin/python` (Python3.12.12). Relevant installed versions include Torch2.7.1, Transformers4.53.3, Diffusers0.35.2, MuJoCo3.7.0, Robosuite1.4.0, LeRobot0.4.2, OpenAI2.8.1. CPU-only imports of the exact new RDT `create_model` and LeRobot processor modules succeeded; LeRobot now resolves into the new worktree. No model was instantiated or loaded for inference.

## Cache and Stage input contract

Historical evaluation reused one alphabet-soup cache across all ten tasks. Its metadata keypoint0 is `alphabet_soup_1_main`; both Stage description lines explicitly name alphabet soup, and Stage2 names basket keypoint1. `main.py` supplied these stale descriptions together with each task's live instruction and live keypoint map. It did not validate task identity. This is an engineering confound, not evidence for a QD mechanism failure or benefit.

Authentic task-specific caches exist for all ten tasks in `/home/hynx/VLA-Pilot++/outputs/libero/2026-06-04_13-21-01/episode_{1..10}/vlm_agent`. However, some historical per-task reward functions differ in AST or return type. Wholesale substitution would change the frozen reward provider. The repair therefore:

- uses authentic per-task metadata, query-image and prompt provenance;
- preserves **byte-identical canonical episode1 stage1/stage2 guidance functions** for every task;
- keeps the canonical Stage description decisions (grasp then move to basket; Stage2 no guidance), replacing only target identity using the BDDL task target and replacing the stale literal basket keypoint1 with a reference to the live mapping;
- labels historical metadata coordinates as provenance only; the recognizer still gets the new episode's actual initial image and live mapping;
- adds only default-OFF `main.require_task_cache_identity` validation in `main.py`, activated by `+main.require_task_cache_identity=true` for every new arm.

The cache identity repair did not change `core/gemini_grounder.py`, `vlm_query/stage_template.txt`, keypoint detection, Stage triggers, VLM model/config, success predicate, reward function, or checkpoint semantics. A later additive request observer in `core/gemini_grounder.py` is described below; it changes none of those decision semantics. The existing Stage extractor produced correct target descriptions for all ten prepared caches. Static inspection shows both initial keypoint images and current Stage images use the same camera,640×640 rendering, and Y flip; no new orientation mismatch was found. Variable keypoint counts remain valid if keypoint0 belongs to the task target and the basket exists elsewhere in the live map. Cached Stage text no longer assumes basket keypoint1.

Relabel new controls `Q0_input_repaired` / `C0_input_repaired` (or record this as an explicit protocol identity alongside frozen profile IDs). Any new result is not a historical-profile replication: cache identity repair and the root's per-task isolated process/RNG policy apply equally to all arms. Rebaseline contemporaneously and do not attribute engineering repair gains to QD.

## Init/seed interpretation

Every init file contains50 rows of110 elements; the existing adapter binds `episode_index=0` for each environment and uses init row0 on reset. Hashes of these actual row0 bytes are recorded. New seeds do not select unseen init layouts. Treat validation as new-seed robustness on the same fixed task/init identities; do not claim unseen-layout generalization. Root's frozen per-task protocol sets policy seed equal to episode seed for all arms and records the departure from historical sequential `seed=0` execution. Task selection is sorted by adapter; one-task subprocesses eliminate schedule/task-order ambiguity.

## Runner contract

Use the new owned runner and independent attempt identities. Never call the legacy runner's `run`, `resume`, runtime mutation, or budget state functions. The runtime manifest supplies:

```text
LIBERO_CONFIG_PATH=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/libero_config
TORCH_HOME=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/torch
PYTHONPATH=/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/lerobot/src:/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/rdt:/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/third_party/libero_pro
HF_HUB_OFFLINE=1
TRANSFORMERS_OFFLINE=1
PYTHONDONTWRITEBYTECODE=1
```

At dispatch only, add `CUDA_DEVICE_ORDER=PCI_BUS_ID`, physical `CUDA_VISIBLE_DEVICES=7`, and the freshly verified EGL device mapping. Keep OpenAI credential/provider injection in the existing process environment after explicit provider binding is resolved. One child runs one task/seed, using the exact manifest task cache, full frozen profile overrides, and these required semantics:

```text
/home/hynx/miniconda3/envs/vla-pilot/bin/python main.py
policy.type=rdt backend=libero backend.libero.suite_name=libero_object_swap
backend.libero.task_ids_filter=[TASK] main.episode_num=1
backend.libero.strict_perturbations=true backend.libero.max_episode_steps=720
seed=SEED main.episode_seed_schedule=[SEED]
policy.rdt.action_chunk_horizon=8 policy.rdt.control_frequency=20
main.use_vlm_stage_recognition=true perception.gemini_grounding.enabled=false
main.cached_functions_dir=TASK_CACHE +main.require_task_cache_identity=true
[complete frozen Q0/P2/candidate profile and owned output/evidence overrides]
```

This is a command contract, not permission to dispatch while the provider or GPU gates are false. Do not omit the complete frozen profile or override checkpoint/provider identities implicitly. The baseline runner owns exact argv serialization, attempt reservation/dispatched/aborted accounting, resource locks, and timeout handling.

## Validation performed

`CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q tests/test_qd_ed_runtime_setup.py -p no:cacheprovider`: **7 passed**. Checks cover wrong task/target/basket rejection, variable live keypoint indices, canonical reward preservation, authentic-cache mismatch rejection, and post-freeze input tampering. Additional read-only checks: all ten prepared caches parse through the unchanged Stage description extractor; all model/input hashes recorded; CPU RDT/LeRobot imports resolve into the owned dependency copies with CUDA uninitialized. No SR or algorithmic effectiveness claim follows from these checks.

## Metadata-only EGL mapping follow-up (10:01 UTC)

Read local installed `OpenGL.raw.EGL` extension declarations before using ctypes to call only `eglGetProcAddress`, `eglQueryDevicesEXT`, `eglQueryDeviceAttribEXT`, and `eglQueryDeviceStringEXT`. No display was obtained or initialized, no context created/made current, and no CUDA library or model was imported by this helper. Metadata enumeration exposed17 EGL device entries (8 NVIDIA CUDA devices,8 DRM entries,1 software entry). `EGL_CUDA_DEVICE_NV` on EGL index4 reported CUDA ordinal7. The full historical NVIDIA map is unchanged: CUDA0→EGL2,1→3,2→1,3→0,4→6,5→7,6→5,7→4.

`nvidia-smi` metadata binds physical GPU7 to UUID `GPU-48473162-9548-1a19-04aa-ea86c5349187`, PCI `00000000:E1:00.0`, driver `580.65.06`. NVIDIA's EGL entry does not expose a DRM file, so direct DRM-PCI cross-check is unavailable (`drm_pci_verified=false`); the CUDA ordinal association is explicit, and the UUID/PCI come from NVML's physical index. Metadata is recorded in owned `runtime/egl-device-metadata.json` and hashed into the setup manifest. Set `metadata_mapping_verified=true`; keep **`cuda_egl_verified=false`** until an exclusively admitted rendering probe succeeds. Metadata confirmation is not GPU admission or authorization to coexist with the external process.

The helper `query_gpu7_egl_metadata()` is explicit-call only and is not invoked by normal runtime setup/import. CPU tests now total **12 passed**, covering absent, failed, ambiguous, and conflicting metadata mappings and ensuring metadata checks never claim a rendering probe.

## Observational whole-episode request accounting

An additive observer on each existing synchronous OpenAI client's HTTPX request hooks counts actual HTTP send attempts, including network failures and internal SDK retries. It does not replace the HTTP client/transport, alter retry settings, mutate request headers, inspect or persist payloads/credentials, change prompts/models/Stage decisions, or draw random numbers. The separate retry count uses OpenAI2.8.1's non-secret `x-stainless-retry-count` header. Total requests include any caller-level retries; the separately classified retry count is SDK retries only. Frozen task caches perform no dynamic guidance calls. Unsupported custom transports report unavailable telemetry instead of fabricated counts.

`main.py` snapshots API counters after policy.reset and before episode preparation. It writes `eds_eval/episode_compute.jsonl` for completed episodes and handled preparation/execution failures, merging the policy's `get_episode_compute_counters()` with Stage/guidance/grounding API deltas. Schema `qd-ed-episode-compute-v1` includes `episode_id`, `task_id`, `episode_seed`, `outcome`, `policy_counters_available`, `provider_counters_available`, `{stage,guidance,grounding}_api_request_attempts`, corresponding `_api_sdk_retry_attempts`, `provider_request_attempts`, and `provider_sdk_retry_attempts`. Stage event records additionally expose per-trigger request/retry counts and availability. Policy fields count actual instrumented DiT/reward boundaries; encoder/perception work must not be silently included in those definitions.

Local MockTransport tests verify500→500→200 means3 requests and2 SDK retries, terminal API failure is also counted, prompts/model/temperature/max_tokens/retry settings remain unchanged, observation attachment is idempotent, unsupported clients report unavailable, and episode snapshots include preparation/failed requests without leaking earlier-episode counts. Targeted tests: **9 passed,6 deselected**. No external HTTP request, GPU or simulator execution occurred. An abrupt process termination can prevent final summary persistence; missing telemetry must remain explicitly incomplete, never become zero cost or a valid result.

`runtime/setup_manifest.json` now declares desired `frozen_stage_provider.credential_env_name=OPENAI_API_KEY`, while `provider_ready=false` remains pending the user's provider binding decision. This is a required source of future credentials, not evidence that the currently injected key belongs to the frozen endpoint.

## Symlink identity correction

The first runner draft validation exposed12 legitimate LeRobot documentation symlinks whose lexical names had been collapsed by the setup fingerprint helper. The generator now retains each lexical absolute path, its resolved path, symlink target text and owned dependency subtree, plus the target's content hash. The regenerated3287-file manifest has unique lexical paths while allowing multiple links to the same target. Every symlink resolves inside its own exported dependency tree. The verifier rejects retargeting even when replacement bytes happen to match. This corrects measurement identity representation, not dependency contents. Setup CPU checks now total14 passed.

## Real CUDA/EGL probe prepared, not executed

`scripts/qd_ed_gpu_probe.py` is ready for a later explicit run after GPU7 becomes exclusively admissible. This task only wrote code and ran12 CPU mock tests. Neither the parent probe controller nor its GPU child has been launched against real hardware. The live manifest therefore still has `cuda_egl_verified=false` and `provider_ready=false`.

The controller shares `data/qd-ed-runner.lock` with episode dispatch, checks GPU7 vacancy and exact UUID twice, refuses unfinished episode/healthcheck state, and uses the common recovery-budget admission with cleanup time, preserving the validation14-hour and formal10-hour reservations inside the48 GPU-hour limit. It records `reserved/dispatched/completed/aborted` health resource events through the runner's existing journal API; health use contributes GPU hours, never episode attempts. The subprocess has its own process group, durable PID/start-tick/boot identity,120-second maximum probe timeout and the runner's5-second exclusivity monitoring. Failure kills only the owned group, records consumed process wall time, and leaves readiness unchanged. SIGTERM triggers cleanup.

The future child will first verify Torch logical0 UUID equals physical GPU7 and run a one-element CUDA tensor calculation. It then creates a64×64 synthetic MuJoCo scene, calls `mj_forward` for static transforms, renders one offscreen frame, and records the actual current EGL display's device index and `EGL_CUDA_DEVICE_NV` association. It records Torch/MuJoCo/CUDA versions, OpenGL vendor/renderer/version, frame statistics and hashes, and a synthetic PNG. No `mj_step`, LIBERO task, RDT/model loading, provider request or download occurs. Evidence must show one visible Torch device, physical GPU7 UUID, actual display EGL4/CUDA7, NVIDIA rendering, correct CUDA result, and nonuniform nonempty image. Only a successful admitted child plus parent evidence validation can set `cuda_egl_verified=true`; the probe never changes `provider_ready`.

Future command (do not run while external GPU7 work remains):

```text
/home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_gpu_probe.py run --manifest /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/setup_manifest.json
```

Mock checks cover wrong UUID/EGL/CUDA mapping, software renderer, empty frames, unwanted simulator transitions, busy-GPU refusal before reservation/dispatch, health-only accounting, failure retaining readinessfalse, success-only readiness updates, preservation of provider status, and rejection of direct child invocation without its admitted parent. A SIGKILL can leave an unfinished health resource; the journal remains fail-closed until its owned process and resource accounting are reconciled.

## DINO perception accounting completion

The policy DiT/encoder counters and HTTP request counters alone omitted the episode's DINO feature extraction. `core/keypoint_detector.py` now counts immediately before the actual DINOv2 `forward_features` and DINOv3 model call. The cumulative `get_compute_counters()` returns `dino_forward_calls` and `dino_batch_rows`; attempts that raise are included, while preprocessing failures before the model boundary are excluded. No detector outputs, preprocessing, model, perception decisions, seeds or random-number draws change.

`main.py` takes perception snapshots alongside API snapshots before episode preparation, persists episode deltas under those two fields, and adds `perception_counters_available` plus `perception_components`. The frozen configuration reports DINO `active_observed`, SAM3 `inactive`, and grounding `inactive`. A live but uninstrumented component reports `active_unobserved` and makes availability false; an inactive component is explicitly identified, so zero calls are not inferred from missing telemetry. Enabled grounding is observed through its HTTP request hook and described as `active_api_observed`. These fields remain in schema `qd-ed-episode-compute-v1`.

Eleven targeted API/episode/DINO CPU tests pass. They cover actual DINO2/DINO3 call boundaries, failures, preprocessing failure, independent counter snapshots, output preservation, unchanged NumPy/Torch RNG state, episode deltas and active-unobserved rejection. A preceding32-test setup/probe/legacy-Stage/API CPU run passed; CUDA lazy initialization was explicitly forbidden and CUDA remained uninitialized. The Stage event observer omits unavailable new fields for legacy test doubles while real observed recognizers provide complete fields. No real GPU probe, API call or task rollout has run.
