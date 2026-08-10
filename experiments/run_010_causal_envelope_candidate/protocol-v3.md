# `run_010_causal_envelope_candidate` Pre-Episode API-Recovery Protocol v3

Date: 2026-08-10 UTC

Parent scientific protocol: `experiments/run_010_causal_envelope_candidate/protocol.md`, commit `1017bf0212780b2e386764517661cf9970090f8d`

Offline repair protocol: `experiments/run_010_causal_envelope_candidate/protocol-v2.md`, commit `8fd3aea0b1ec063aba63fa0bffcf3829f03c006c`

Frozen scientific execution revision: `d018f8acb12263d81c65f8eb717f9c987459e991`

Scope: one audited exact-cell recovery from an API health-check failure that occurred before worker or episode initialization. This amendment changes no algorithm, config, task, seed, checkpoint, manifest, budget, metric, threshold, promotion rule, or formal authorization.

## Observed incident and classification

The first mechanism-preflight command completed storage, credential-presence, two-snapshot GPU admission, and dispatch reservation, then the base runner's Poe Gemini health check returned false and raised `Poe Gemini health check failed`. The command ended before `base.run_level` initialized a worker or episode.

Immutable evidence at protocol lock:

- attempt ledger SHA-256 `4e255f9380feb5a7c395002c8693ee0be813d2033426e23a343e02cdbc3f30ce`; it contains episode reservations 1–6 and one dispatch event;
- GPU admission SHA-256 `53db933fe0c2394643b36d2d76c39f8ec49558cc62e976e8e8cffa472c5ce579`; GPU 7 / UUID `GPU-48473162-9548-1a19-04aa-ea86c5349187` was idle in both admission snapshots and the immediate dispatch snapshot;
- the run root contains only the two immutable offline-preflight files, immutable run manifest, attempt ledger, GPU admission, and runtime-cache provenance; it contains no online output directory, `run_manifest.csv`, phase status CSV, runner log, failure record, or episode metric;
- shell wall time was 39.2 seconds, including the 30-second admission interval; no task-level observation or policy outcome exists.

This is an `API transient / pre-episode infrastructure abort`, one of the parent design's explicitly recoverable categories. Attempts 1–6 must remain append-only evidence and receive a `dispatch_aborted_pre_episode` event before any replacement reservation. They do not enter success, failure-taxonomy, mechanism, latency, GPU-hour, or actual episode-attempt denominators.

## Exact recovery authorization

Exactly one recovery dispatch is authorized for the same six cells:

| Profile | Task | Seed | Recovery of |
| --- | ---: | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 3 | 512905 | 1 |
| `p2_stage_on_abs_rbf_control` | 5 | 150741 | 2 |
| `eds_quality_diversity_sparse_primary` | 3 | 512905 | 3 |
| `eds_quality_diversity_sparse_primary` | 5 | 150741 | 4 |
| `eds_quality_diversity_sparse_causal_envelope_v1` | 3 | 512905 | 5 |
| `eds_quality_diversity_sparse_causal_envelope_v1` | 5 | 150741 | 6 |

Recovery procedure:

1. Append one `dispatch_aborted_pre_episode` event for IDs 1–6, with this protocol commit, both evidence hashes, and the API-health classification.
2. Confirm `.autoresearch/PAUSE` is absent, owned storage is valid, the immutable manifest SHA-256 remains `cb211e2ed3fe2cfa2512f0982153295c9f23fa9964e3f623d1ef3b1eef10ae34`, and no online artifact exists.
3. Temporarily execute the recovery from the frozen scientific revision `d018f8acb12263d81c65f8eb717f9c987459e991` inside this same worktree so the six recovered cells retain code-state `3626b52b619d6c951aee48f07c206ce5af44dff8cf12fad40d85ab01c9a9839c`, the original three profile fingerprints, and identical algorithm source/config/checkpoint/job bindings. The target branch retains this protocol commit and is restored immediately after the command.
4. Run `base._poe_healthcheck()` before GPU admission and before creating recovery reservations. If it fails, stop without appending IDs 7–12.
5. Dynamically admit GPU 0–7 again with two snapshots and an immediate dispatch snapshot. Do not reuse the first admission decision or co-locate with external compute.
6. Append recovery reservations 7–12 with the same task/seed/config/code/checkpoint identity and explicit `recovery_of_attempt_id` / `recovery_reason` fields, then append their dispatch event and admission artifact hash.
7. Because the same Poe health check has just passed and the base runner otherwise repeats it only after reservation, replace only that redundant in-process call with the already-passed result for this dispatch. This is transaction plumbing only; all VLM calls made by episodes remain online and unchanged.
8. Run the original frozen `max_chunks=2` mechanism-preflight jobs and audit them with the parent gates. Preserve every raw artifact and append task-level outcomes to the canonical ledger.

The inline recovery wrapper may call only existing committed functions from `scripts/eds_qd_autoresearch_runner.py`, `scripts/eds_quality_diversity_runner.py`, and `scripts/rdt_eds_eval_runner.py`; it may not edit a source file or manifest. Before dispatch it must assert that recovered task/seed/profile/code identities equal attempts 1–6 except for attempt ID, timestamp, and recovery provenance.

## Stop conditions

- A failed pre-reservation health check creates no new attempt and pauses for infrastructure review.
- A second failure before any worker/episode start preserves and aborts IDs 7–12, then stops; v3 authorizes no third dispatch.
- Any worker-started policy timeout, collision, drop, wrong-object interaction, qpos error, or other task outcome is not retried.
- Any task/seed/config/code/checkpoint/manifest mismatch invalidates recovery before dispatch.
- Mechanism PASS alone authorizes only the already-frozen Dev-A gate. Dev-B, validation, and formal evaluation remain unauthorized.

## Target and budget impact

Historical EDS-QD best remains `2/10`; target gap remains 3. This amendment cannot improve success and exists only to recover the first valid mechanism evidence. The six aborted pre-episode reservations remain visible, while the replacement cells consume at most six of the 15 infrastructure-recovery slots. Actual episode attempts remain 0 until a recovered episode initializes; global caps remain 143 attempts and 48 GPU-hours.
