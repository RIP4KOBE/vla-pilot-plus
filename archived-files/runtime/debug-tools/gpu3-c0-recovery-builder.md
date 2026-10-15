# Explicit GPU3 C0 infrastructure-recovery draft

Builder SHA256: `a07c16c9b0a7099f96b9f82cf17d5380ed8fae0b9a403c19a5c35cdf968b3e17`.

Six CPU tests passed in 0.03 seconds. This preparation did not create/freeze a plan,
change state/source, commit, query GPUs, or dispatch anything. The builder writes only
an explicitly named, new **unfrozen** artifact draft. It does not run full model hashes.

The parent attempt and new key are mandatory arguments. The builder reads the named
parent's unique ledger identity, checks its consistency and equality to the original
C0 identity, then applies the existing runner `check_retry`. It never selects the
latest attempt automatically. A retry reserved by another worktree is already
consumed; no key/iteration substitution can bypass that check. The original parent
`6e57273c45b3` remains consumed. The subsequently infrastructure-aborted parent
`03c5d2b4a1df` is the explicitly selected parent for r2, subject to fresh ledger checks.

Root-owned build command, after runtime/protocol preparation:

```sh
python /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/build-gpu3-c0-recovery-draft.py \
  --source-head e131ff67f97a5da7fd68d1dd9a8dfe6e08253dea \
  --runtime /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/gpu3-render-diagnostic/runtime-manifest.json \
  --protocol experiments/iteration_001_execution_intent/gpu3-render-timing-diagnostic.md \
  --retry-of rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00_r1__03c5d2b4a1df \
  --episode-key gpu3_native_c0_t00_r2 \
  --output /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/gpu3-c0-r2-plan.draft.json
```

The resulting plan has one dev row, iteration `GPU6_NATIVE_C0`, profile C0, task 0,
both seeds 1969522881, init 0, timeout 1800, and recovery bucket. Other phase gates are
false. It removes diagnostic_only, native queue/probe contracts, stale hardware and
preview references, and active candidate profiles; it contains no N1 episode.

All runner-required code, scientific config/protocol files, and the four observation
patch files are fingerprinted. Files must equal the specified committed HEAD.
Non-observation source/config hashes must also equal the native base plan; protocol
documents are allowed to change. Runtime physical GPU must be 3; nonhardware runtime
fields and file inventory must match the base runtime. Profiles, seed plan, model
inventory hashes and Stage/input condition must match the original C0 plan.

Runner interfaces, from the worktree:

```sh
python scripts/qd_ed_final_runner.py validate-plan --allow-unfrozen --plan <draft-path>
python scripts/qd_ed_final_runner.py print-command --allow-unfrozen --plan <draft-path> --split dev --iteration GPU6_NATIVE_C0
```

Both are CPU only. `validate_plan(..., require_frozen=False)` still verifies current
HEAD, all code and runtime file hashes, run/artifact ownership, GPU state binding,
provider contract, profile, seed and init identity. It skips full checkpoint/encoder
byte hashing and readiness requirements. Final frozen validation additionally
requires verified EGL mapping, provider readiness, and all model bytes. Leave that
full pass to the queue once; the builder never calls provider verification or GPU APIs.

Configuration preview uses `runner.build_command(plan, manifest, runtime, row,
'PREVIEW__gpu3_native_c0_t00_r2')`, followed by Hydra `initialize_config_dir` with the
worktree configs directory and `compose(config_name='config', overrides=argv[2:])`.
This does not import main or instantiate a model/environment. To save resolved values,
select only the override keys from argv (strip leading `+`; map the `backend` group
to `backend.backend`). Resolve individual selected OmegaConf values and convert
selected list/dict values with `OmegaConf.to_container(..., resolve=True)`.
Do not serialize the entire resolved config or inherited environment, which may
contain unrelated credential fields. The public hardware preview is separately
`CUDA_VISIBLE_DEVICES=3`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `MUJOCO_GL=egl`,
`PYOPENGL_PLATFORM=egl`, and `MUJOCO_EGL_DEVICE_ID` read from the supplied runtime.

Root owns final preview, readiness review, freeze timestamp/flag and final output.
This builder does not reserve a retry or hold a lock across root's later freeze;
the existing runner/queue must recheck ledger, budget, idle/exclusive GPU3 and source
under its normal locks at dispatch. Any intervening consumed retry must fail closed.
