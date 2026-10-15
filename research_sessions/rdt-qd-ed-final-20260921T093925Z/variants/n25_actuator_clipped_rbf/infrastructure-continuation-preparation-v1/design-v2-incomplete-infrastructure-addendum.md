# N25 continuation design v2: one named incomplete-infrastructure retry

**Design only; no implementation or release.** This separate addendum preserves design-v1 and its delivery hashes. It changes only the prerequisite for one specifically named failed primary. All other v1 restrictions remain, including immutable original INVALID history, independently sealed 18-cell prefix, exact unrun suffix, unchanged science/Stage/Codex/E2 settings, combined limits/costs, no local-time reset, one launch, and immediate closure on any further invalid outcome. N25 validation and N26 remain inactive.

## New provisional terminal information

The parent reports the original attempt ending `__n25_dev_t04_n23_20260930__8b236af507d8` has:

- literal terminal `event=valid`, `outcome_valid=false`, `reason=TimeoutExpired`, `compute_outcome=completed`;
- charged GPU process wall time `1801.4751812220784` seconds;
- 43 logical calls, 37 completed calls, 6 failed calls, 37 usage-complete calls;
- six observed 180-second Codex transport timeouts with stream_error/item_error lifecycle evidence, plus whole-worker 1800-second timeout;
- missing `eds_eval/in-worker-audit-receipt.json` and `eds_eval/decision-evidence-audit.json`;
- present `results.txt` and `eds_eval/episode_compute.jsonl`;
- the old supervisor's recovery eligibility fails with FileNotFoundError, rather than accepting this under its original classifier.

These values are supplied by the parent and remain provisional until its immutable terminal review. No actual file, log, ledger, process or payload was read by this task. The eventual full attempt ID, complete raw terminal field names/values and all refs must be taken exactly from that review; ellipsis in a narrative is never a wildcard. No automatic acceptance of a similar future signature is proposed.

V1 correctly blocks this case because its completed native-audit requirement is unmet. `compute_outcome=completed` and an on-disk results file do not prove full worker completion, safety, source/native arithmetic validity, accepted task outcome, or an audit finishing before timeout. The `event=valid` label must remain literal alongside outcome_valid=false; it is not an accepted scientific result.

## One explicit exception, with Unknown preserved

Prospectively freeze a separate **named incomplete-infrastructure exception** for exactly this one task4/N23 attempt. Its permissible historical signature is the root-confirmed conjunction of the enumerated Codex failures, whole-worker TimeoutExpired, completed compute marker and absent receipt/report—not a generic timeout, missing-audit or invalid_resolved rule. It authorizes a single repeat, not acceptance or repair of the old episode.

The six API timeouts are observed; they do not establish that API failures were the sole cause of the worker timeout, missing audit, or other unmeasured behavior. Native arithmetic, full audit, safety/semantic gates not independently measured, and causal attribution remain explicitly **Unknown**. Do not require or manufacture an assertion that every non-provider gate passed. Nor may absent evidence be rewritten as passed, zero or not applicable. Contradictory positive evidence of a different fault must be disclosed and referred back to root; it is not silently absorbed into this exact exception.

The future `n25-named-incomplete-infrastructure-proof-v2` should therefore replace the v1 proof requirement for this one successor protocol only. It binds:

1. Original immutable plan/source/runtime, root terminal review/result, Dev-only settled ledger and exact failed attempt/process/terminal/context refs.
2. The exact observed terminal/event/invalidity/cost fields and root-enumerated per-call lifecycle signature; all present metadata hashes and typed absence records for the two missing audit files.
3. Explicit `original_outcome_valid=false`, `original_cohort_disposition=INVALID_OR_INTERRUPTED`, `native_audit_status=UNKNOWN_MISSING`, `all_non_transport_gates_verified=false`, `api_only_causal_attribution=UNPROVEN` and a list of unmeasured gates. These are honest limits, not successful eligibility verdicts.
4. The old classifier's rejection/exception and reader/source identity, with no changes to its code or result; the exact prospective exception/protocol reference; `maximum_named_retries=1`, `accept_original_as_scientific_result=false`, `retroactive_native_repair_authorized=false`.

All references remain unresolved in this design. Authority/plan/source review must reference this new v2 proof and addendum explicitly; an old v1 proof or release cannot supply the exception. Original v1 records remain historical and blocked for this signature.

## Bounded metadata-only root checks before freezing

Use the original source while it is still intact to seal the 18 independently accepted cells, retaining every original attempt and cost. Separately establish that the failed primary has exactly one reservation/dispatch/settled terminal and no prior retry. Bind its original profile/task/seeds/init/source/plan/runtime identity from available records; do not infer missing fields from the desired outcome.

For the failed attempt, root's bounded review can compare existing public command/process lifecycle, PID/start ticks/boot and exit/timeout/cleanup evidence; confirm that the 1800-second limit is the original worker deadline and that the `1801.4751812220784` wall charge is retained in full. Confirm controller/worker and owned descendants have exited and no native audit is still writing. A terminal ledger record alone is not proof of process death. If cleanup is incomplete, defer release; do not start a concurrent worker or change recorded elapsed time.

Record each absent audit artifact as `{path, present:false, sha256:null}` only after settlement, and recheck that exact absence at final review/release. If a delayed writer creates one, the frozen absence proof is stale and must fail closed; do not silently classify it as a retrospectively accepted audit. Hash present results/compute/process/context files as evidence of presence and identity without interpreting their contents as a passing audit. These checks authorize neither tensor replay nor post-hoc GPU audit.

Freeze the actual six failed-call identities and lifecycle types/order, successful-call counts and available usage counters from the root's finite forensic evidence. Preserve any partial/message/completion records exactly rather than assuming none existed. If 43 logical and 37 usage-complete calls are confirmed, six calls have unknown usage; totals remain observed partial values, not six zero-token calls. Missing cost/compute fields stay missing. Do not make the stronger claim that all remaining gates reconciled merely because the reported counts agree.

Root must certify old controller terminal/result settlement and no later original row reservation. At that point the original cohort remains immutable INVALID. The new plan carries only the already audited prefix and the one exceptional repeat plus original unrun rows. It does not import this failed primary as one of the 40 accepted cells.

## Retry, accounting and terminal behavior unchanged

The named repeat uses the identical task4/N23 scientific settings and seeds, a new operational cohort/key/attempt ID, `retry_of` equal to the original failed attempt, and the recovery bucket. Whole episode 1800+40 seconds, GPU7, original current-Codex login/Stage E2/180-second calls, original provider/profile/source/native audit gates and no Poe fallback remain unchanged. The new episode must satisfy every original normal acceptance gate, including its in-worker receipt and independent native report. No “expected timeout,” missing audit, partial tokens or weaker special acceptance is allowed in the repeat.

A valid task failure in the repeat counts as a scientific failure and proceeds to the original untouched suffix. Any invalid repeat stops. Any later invalid also stops, even a pure timeout that the old protocol might otherwise have recovered. No second exceptional retry, automatic resume, generic missing-audit recovery or native preflight is proposed. Old-invalid plus retry cannot produce two accepted observations for one cell.

Every old and new attempt is charged exactly once; the old 1801.4751812220784-second charge and unknown usage are retained. The complete matrix still has 40 logical cells with 18 immutable imports and at most 22 new dispatches; all combined original/new attempt and recovery ceilings, existing adopted finite bucket caps, original local-hour ceiling and protected reserves remain as in v1. New local time is the remainder, never a fresh allowance. Insufficient full 1840-second per-dispatch capacity closes or blocks as INVALID/incomplete.

Whole-quadruple futility and complete-40 promotion are unchanged. The original failed attempt is never retroactively made valid and the original cohort is never relabeled REJECT. A later valid logical-cohort aggregate would still require separately reviewed evidence/source adapters for prebuilt N25 validation and N26 predecessor gates; current engineering INVALID satisfies neither.

## Additional proposed synthetic checks

Once root freezes a concrete protocol and separately authorizes implementation, add exact named-signature acceptance alongside rejection of a different attempt, mismatched counts/types/deadline, unexpected fault, consumed retry, changed present/absent artifact, delayed writer, live owned worker, incomplete settlement, and a valid prior scientific outcome. Verify the proof exposes Unknown rather than claiming full historical audit, while any missing native receipt or normal-gate failure in the **new** attempt remains fatal. Preserve all v1 mapping/source/capacity/status-failure tests. None were executed in this design task.
