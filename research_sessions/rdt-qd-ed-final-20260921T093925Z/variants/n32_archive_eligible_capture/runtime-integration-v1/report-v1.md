Committed CPU runtime integration `260f19ed29c38aa1c361fda50acb3abdf7fb0af0` (parent `148d1aae182500df04d0fa8b13fc54bc533e56a7`) in the isolated implementation worktree. Status: pending root review; no release or efficacy claim.

N32 now uses the accepted pure selector at the existing post-rollout/pre-score boundary. Every occupied archive cell is associated with same-decision canonical iteration, fingerprint and exact native bytes; duplicate occurrences must agree in quality, cost, original projection and source/cast origin. Only the highest-ranked eligible parent's unchanged N31 transformation replaces slot15. No eligible parent returns the ordinary population unchanged. The separate mode defaults off and rejects missing provenance or mixed N31 configuration.

Main binds the observed adapter task ID to the configured task. Runtime records bind task/run/declared source, resolved config digest, actual on-disk implementation hashes, decision/provider/packet/tracker/target identities, canonical scoring sources and executed action identities. The new independent reference enumerates and ranks all reconstructed parents without calling the production selector or proposal helper; it uses the frozen independent N31 mathematical reference. The frozen N31 auditor, helper, cache implementation, accepted N32 selector, ordinary QD archive and generic recorder/auditor are unchanged.

Validation: **48 final N32 tests passed**, plus **150 existing selector/N31 regression tests passed**. Final N32 suite: 54.506s wall, 72.404s CPU. CUDA was hidden; OMP/MKL/OpenBLAS each had two threads; every pytest process had a 1200s CPU limit and 300s wall timeout. All test invocations exited 0. Existing `fkd_class.py` invalid-escape SyntaxWarnings remain. Final static compilation and diff-whitespace checks exited 0. Elapsed time since scope creation (an upper bound on executor time) was 858.8s when this report was written.

Coverage includes float32/bfloat16; best-ineligible/secondary-eligible; best-eligible exact N31 parity; no-eligible complete Q0 population/action/RNG/call/projection-observation parity; ties; duplicate content; all-parent enumeration; missing/contradictory provenance; decision/source/task/config mismatches; parent/slot15/other15/cost/projection/origin/mask/RNG/retention/execution tampering; actual Main packet path; Hydra config composition; in-memory native recording; and disk-backed independent audit with required trusted binding. No external services ran.

Exact test argv, log hashes, per-process final resource measurements, changed-file current/parent SHA256 values and unchanged invariant SHA256 values are in [result-v1.json](result-v1.json). Initial checkpoints passed 25, 15 and 45 tests while the suite was extended; the final 48-test N32 run supersedes them. The 150 regression tests exercised unchanged N31 and mode-off behavior; the final N32 run also covered the final nested-transfer/config-parsing corrections.

Measured synthetic per-decision costs (10 opportunities; seconds):

| dtype | selector process CPU | explicit transfer/sync wall | N32 recording wall |
|---|---:|---:|---:|
| float32 | 0.109964 | 0.025823 | 0.010625 |
| bfloat16 | 0.118985 | 0.026280 | 0.008666 |

Evidence contract:

- `runtime_mode`: archive_eligible_capture_v1; separate archive_eligible_capture_mode defaults off; mutually exclusive with capture_dwell_proposal_mode.
- `configuration`: n32_runtime_binding = {task_id: nonnegative int, source_commit: 40 hex, run_id: nonempty str}; resolved config serialized with sorted JSON and SHA256.
- `envelope`: existing DecisionEvidence sequence, decision_id, episode, global_step, reset_sequence; native tensor snapshots keep original dtype.
- `n32_observation_context`: cached raw packet including adapter task_id, keypoints, observed EEF, hand quaternion, jaw qpos, tracker instance/generation/target; bound to provider template identity and policy context.
- `n32_canonical_cache`: 11 batches, 176 occurrences max: scoring batch ID, role/site/iteration, mask, native plan identities, original outcome positions1:9, source/cast origins, original projection status; plans/rewards/costs linked to generic canonical/scoring events.
- `n32_archive_eligible_opportunity`: ten opportunities: all occupied cell parent records and full native canonical source, all matching occurrence IDs, eligibility reason/arrival, winning cell or null, transformed candidate or null, full ordinary post-rollout and actual scored populations, prepare/apply CPU and optional device RNG snapshots, identity/binding/resolved config/config digest/source hashes, raw packet.
- `n32_archive_update`: 11 ordinary native cell assignments, descriptors, fixed bounds, retention snapshots, parent cell IDs; independently replayed reward/fingerprint ties and insertion sequence.
- `final_execution`: generic final_selection, policy_action_decode, decision_committed, executed_action, pre_reset_outcome, step_returned; final archive global best and executed prefix independently verified.
- `scalar`: capture_dwell_proposal metric key with schema n32-archive-eligible-scalar-v1 and explicit N32 mode, counts/reasons, labeled aggregate overhead, selector CPU/transfer-sync/recording costs, Unknown provider HTTP telemetry.
- `audit`: scripts.qd_ed_n32_native.audit_events/audit_output/from_output/counts; GATE n32_capture_dwell_audit; schema n32-independent-capture-dwell-v1; expected_runtime required for N32; no production selector/helper calls.
- `reference`: scripts.qd_ed_n32_reference.enumerate_parents independently ranks all reconstructed archive entries; frozen independent N31 binary64 reference reconstructs unchanged geometry.

Limitations and remaining proof gaps:

1. CPU synthetic validation only: no GPU, model weights, simulation, Dev episodes, protected validation/formal result access, historical payload analysis, cloud or external provider/model calls; no efficacy or scientific promotion.
2. CUDA branch is implemented but unexecuted. Native CPU copies and device restoration preserve dtype by construction; CUDA transfer, synchronization, allocator behavior, device RNG observations and total GPU latency remain unmeasured.
3. Independent auditor inherits original native cell assignments, projections, provider outputs and bounds; independently replays all-parent association/geometry/ranking, retention and final execution decoding, not GPU descriptor arithmetic or physical motion.
4. RNG and other15 evidence are local boundary snapshots, not independent replay of model/noise generation. CPU comparisons establish schedules on the tested fake services, not arbitrary provider or model behavior.
5. A separately reviewed expected_runtime manifest (binding, resolved config SHA256, source hashes) is mandatory to accept N32 audit gates. Test fixtures derive only their config digest from their own synthetic trace; this is not a production trust anchor.
6. source_commit is a declared, externally checked binding; hashed on-disk implementation modules and Main are checked against the caller manifest. Live loaded bytecode, full dependency tree, checkpoint identity and launcher/checkout attestation remain release responsibilities.
7. First-decision raw observation provenance and actual environment/controller execution beyond recorded actions retain generic evidence limitations. Content agreement and a single matching occurrence never establish unique ancestral lineage or successful capture.
8. Fail-closed N32 rejects absent recognized provider, packet/tracker, task or canonical projection provenance; these are not counted as geometric abstentions. N31 and mode-off retain their existing behavior.
9. Audit compute expectations retain the frozen 11 canonical plus five auxiliary scoring batches per guided decision. A different runtime schedule requires separate review, not relaxed auditing.
10. Measured transfer_sync_seconds covers explicit prepare/apply CPU copies and device round trips; recording_seconds covers synchronous N32 cache/opportunity records. Inherited canonical-cache work and other synchronization are included in aggregate overhead but not separately attributed. Main packet capture, recognition/validation, origin copies, archive snapshot observer, whole-selection costs and source hashing are excluded as labeled; persistence/flush costs remain in the generic recorder status. These timing scopes overlap and must not be summed as total runtime cost.
11. Provider HTTP telemetry remains Unknown. No assumption that unknown or unmeasured GPU/provider overhead is zero.
12. Candidate config is a template requiring explicit task/source/run binding. No supervisor/driver/coordinator adoption, GPU release, owning source/tree/ledger write, budget change, or scientific score is delivered.

No owning scientific source, coordinator state/tree/ledger/driver, or histories were modified. All implementation changes are committed; reports and test logs are confined to this runtime-integration-v1 directory. Root review is required before any further release.
