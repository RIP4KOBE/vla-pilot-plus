The failure is a Hydra schema registration defect. `configs/config.yaml:69–85` defines `main.eds_config` but omits `diversity_update_mode`. The exact N27 expansion in `scripts/qd_ed_n27_contract.py:328–342` emits the ordinary override `main.eds_config.diversity_update_mode=feasible_ray_v1`; `qd_ed_final_runner.py:976–1020` serializes it unchanged. Hydra's struct check therefore rejects it before the decorated main body can run. `main.py:2246` uses this exact `configs/config.yaml` entrypoint. This is not evidence of algorithm efficacy or failure.

The smallest proposed repair is the one added line in `proposed-config-default.diff`:

```yaml
diversity_update_mode: legacy_additive
```

The disabled spelling is established by `core/qd_feasible_ray_rbf.py:8–17`, `core/rdt_policy_steer.py:133`, and the loader fallback at line7983. `none` would be invalid. The N27 profile/strict rule continues to select `feasible_ray_v1`; the existing N27 predicate still rejects wrong mode or modified active settings. Changing all overrides to Hydra `+` would hide schema errors and is unnecessary. The proposal changes only an external config copy; frozen I27/W/configs are unchanged.

CPU evidence

The scope inventory contains exactly25 static files,885,076 bytes; their SHA-256 values are in `static-inputs-v1.json`. Original source functions were extracted as unchanged AST definitions with explicit pure dependencies, including actual candidate expansion, `build_command`, Codex public-policy and E2 override checks. No original module top level, main, core policy, model or environment was imported. Synthetic public runtime/row values replace closed actual metadata; no login or executable was inspected or invoked.

Installed Hydra1.3.2 and OmegaConf2.3.0 executed the real composition path for the complete original four-arm argv, stored in `synthetic-build-command-argv-v1.json`. Each same argv was composed against the old and one-line-patched copies:

| Arm | Old schema | Patched schema | Effective EDS mode |
|---|---|---|---|
| C0 | passes | passes | legacy_additive |
| Q0 | passes | passes | legacy_additive |
| N26 | passes | passes | legacy_additive |
| N27 | expected struct rejection | passes | feasible_ray_v1 |

The N27 old-schema exception matches the reported missing-key error. For every control, the entire composed configuration is structurally identical after removing the new disabled key, and the resolved EDS dictionaries are equal after that same removal. N27 versus N26 has exactly one resolved EDS difference: the feasible-ray mode. The old missing field and the new explicit control value also both pass the unchanged source disabled-mode predicate. Hydra still rejects an unrelated missing option; the unchanged source predicate rejects `none`, an unknown mode and population15. No broad numerical test was repeated.

The full configuration comparison uses `resolve=False`; `${hydra:...}`/`${now:...}` are not evaluated. Only the interpolation-free EDS subtree uses `resolve=True`. This proves configuration/schema and effective EDS equivalence, not execution, scheduler behavior, native arithmetic or task success. The pure-source AST extraction identities are listed in `cpu-result-v1.json`; the small imported Hydra/OmegaConf dependencies are the only runtime configuration libraries.

The first CPU invocation failed in the new extraction harness before composition because it omitted `_REMOVED_ENVIRONMENT`, a pure constant used by the existing public policy helper. `check_hydra_cpu_v1.py`, `guard_cpu_v1.py` and its failure log remain preserved. Version2 includes that helper's actual constant dependencies. It completed all8 main compositions and the additional unknown-key negative composition, plus8 explicit parity/predicate checks. Both runs had guard0, CUDA hidden, Torch absent, two-thread environment; aggregate elapsed time is recorded in `cpu-test-results-v1.json`, below60 seconds. No real attempt, outcome, tensor, Stage, state, budget or private ledger was read.

Why the secondary recovery exception is expected

At `qd_ed_final_runner.py:1929`, a nonzero child exit raises before successful native receipt binding. `failed_outcome` at1706–1734 may retain the literal ledger event `valid` and task-failure label for this class of exit, but it sets `outcome_valid=false` and `required_cost_telemetry_complete=false`. These literal legacy fields must be preserved; `event=valid` does not make it an accepted scientific failure. The finally block at1958ff still measures and journals the owned process wall time, including startup and abort.

The supervisor at `qd_ed_n27_supervise.py:58–65` attempts the frozen typed-timeout classifier for any invalid primary. `qd_ed_n27_recovery.py:59–69` first requires the terminal's metered receipt binding and native evidence. A setup/struct failure lacks the required successful full-episode audit/telemetry and cannot satisfy that condition. The message `N27 primary terminal/metered audit differs` is therefore a secondary fail-closed gate, not permission to retry and not proof of a Codex timeout. The root-reported7.231457-second startup cost remains charged. Missing counters/usage stay Unknown; do not infer numeric zeros from missing telemetry or rewrite the original event/failure label.

A future controller can make the error clearer by detecting absent successful metered evidence before attempting the old sole-timeout classification and recording `not eligible: setup/config failure` as an additional explanation. It must retain the original terminal and error, close INVALID, and leave the original classifier unchanged. This is a proposal only; no recovery/controller code changed here.

Conditional continuation and minimal bridge

Root reports the old cohort is independently closed as `INVALID_OR_INTERRUPTED`, with3 valid task0 controls, one invalid N27 startup and verified cleanup. Those facts were provided by root, not inspected in this task. The scientific configuration equivalence above supports prospectively inheriting the three independently sealed controls without rerunning them. It does not retroactively validate the original N27 attempt or authorize a continuation.

The root's proposed narrow accounting is consistent with that scope: exactly13 new dispatches—one explicitly named infrastructure replacement of the invalid N27 task0 charged to recovery, then the12 original unrun rows (3 baseline,9 development). Combined history is17 attempts for at most16 accepted cells. There is no extra retry. Original3 valid controls and the invalid attempt/cost remain immutable; the replacement must pass every original complete outcome/native/provider/receipt/cost check. Any new invalidity closes the new continuation; neither incomplete results nor engineering INVALID may pass a scientific gate. No budget expansion or reallocation is needed for those stated slots; actual current capacity/resource/protected reserves remain root admission checks.

A new source bridge must bind the exact old095 source record, accepted old36-case proof and terminal/prefix seal, the new source record, and the precise `configs/config.yaml` old/new hashes and one-line reverse patch. All scientific/core/helper/native/reference/profile bytes must remain identical. Only separately reviewed administrative runner/worker routing may be additional source deltas. Compare full four-arm argv and the config-equivalence evidence in this delivery. Preserve the old proof's original source identity; never relabel it as a new proof or silently bypass its exact-source gate. A prospectively approved bridge must explicitly carry the unchanged arithmetic evidence through the schema-only change and future named continuation routes. There is no reason in this single-line repair evidence to rerun the36-case GPU proof; this CPU task neither reruns nor releases it.

Original result/status, all4 attempts and costs remain closed. A separate combined logical-cohort result must identify inherited versus new cells and all17 attempts, apply the unchanged16-cell screen gate, and remain distinct from the original INVALID result. Source bridge, new authority, fixed suffix, process cleanup, budget and terminal-reader support require separate root review. No continuation implementation, source adoption or execution has been performed by this delivery.
