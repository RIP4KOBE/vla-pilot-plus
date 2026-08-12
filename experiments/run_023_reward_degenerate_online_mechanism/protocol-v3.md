# Recovery Protocol v3 — run_023 global-offset ledger repair

Status: `LOCKED AFTER PRE-DISPATCH INFRASTRUCTURE FAILURE AND BEFORE LEDGER MUTATION, RUNNER REPAIR, MANIFEST V3, OR REDISPATCH`

Parents:

- scientific protocol commit: `73724cec4d8c60096e5c6baed46274c7098964a3`
- manifest-v2 recovery protocol commit: `70678d207d7196f4b6ae9adfb524b67970dce047`
- manifest-v2 implementation commit: `ac43b87`
- immutable manifest v1 SHA-256: `d51a44042357b129595cc220faeecd5a9029f2424e0b803711a32ed31a8ec718`
- immutable manifest v2 SHA-256: `8e47ebb3ddcdf4f9b3657d5585902b303d35fa2162e597e2faf1b7d87805d2df`

## Audited incident boundary

Under explicit user authorization, the replacement credential was passed only in the detached Run023 process environment. Its value, fragments, headers, response, hash, and fingerprint were not printed or written to worktree, artifact, command line, manifest, ledger, documentation, or Git. The real Stage/Poe health check passed.

Fresh two-snapshot admission selected idle GPUs 2 and 5 and wrote immutable admission artifact SHA-256 `9ff20450a39d98e9a9771cad16688990d57381a432b7677247e55b1fb7a35cbe`. The runner then appended exact global reservations 55–60. Before `phase_dispatch`, worker creation, model load, LIBERO reset, episode, metric, video, or task outcome, the legacy ledger event helper rejected these records because it assumes every standalone ledger begins at local ID 1 rather than the frozen global offset 55.

The six-line ledger prefix is preserved with SHA-256 `6d586f32c840c87a61e3e179b2ab670756e5b734aa88fdc6cf522e5be56247af`. It contains only IDs 55–60, has no event, and has no output tree. The immutable runtime log SHA-256 is `fdd858a0556c97b9808b76e8f15d0deceff3d8d7f482e524553a91cd2433b19c`. This is `INFRASTRUCTURE_FAILURE / RESERVED_NOT_DISPATCHED / ZERO_EPISODES`, not algorithm or task evidence.

## Frozen recovery

This amendment authorizes one exact-cell infrastructure recovery using six of the 19 reserved recovery slots:

1. append one `reservation_void` event for IDs 55–60; never delete or rewrite those lines;
2. repair only the Run023 dedicated runner/test to validate an attempt ledger whose first global ID is 55, append global-offset events, and bind `recovery_of_attempt_id=55..60`;
3. create immutable `mechanism_manifest.v3.json`, preserving v1/v2 and binding this protocol, the incident ledger/admission/log identities, the unchanged science, and recovery IDs 61–66;
4. repeat real health and fresh two-snapshot admission;
5. only then reserve IDs 61–66 for the identical six cells and append a dispatch event using the repaired helper;
6. run and audit the unchanged control/candidate jobs.

After recovery reservation, global reservations are 66/143; six recovery slots are consumed and 13 remain. Unique scientific cells remain six. IDs 55–60 are void pre-dispatch infrastructure records and do not count as scientific execution.

## Authorized source boundary

Only these files may change after this protocol commit:

- `scripts/eds_qd_autoresearch_v2_runner.py`
- `tests/test_eds_qd_autoresearch_v2_runner.py`

The repair may add a global-offset ledger reader/state/event writer, recovery reservation metadata, v3 manifest binding, and focused tests. It may not modify the legacy runner, core/config, algorithm, profile, command science, tasks, seeds, horizon, checkpoint, LIBERO/cache inputs, model/reward/VLM call budget, thresholds, audit gates, or formal authorization.

The four frozen algorithm/config SHA-256 values must remain unchanged. V1 and v2 manifests remain `0444` at their exact hashes. Runner/tests must pass and be committed before v3 freeze.

## Stop and decision rules

Health/admission failure before IDs 61–66 consumes zero additional reservations and may wait for infrastructure only. A further local pre-dispatch code failure stops Run023 for outer-loop infrastructure review; it does not authorize another repair or reservation set. Scientific/mechanism/task failure is never retryable.

On valid completion, the original Run023 mechanism, safety, latency, artifact, accounting, and credential gates remain authoritative. PASS may authorize a Dev-A protocol only; FAIL concludes H2 online mechanism with no Dev. Dev-A/B, validation, and formal remain unauthorized now.
