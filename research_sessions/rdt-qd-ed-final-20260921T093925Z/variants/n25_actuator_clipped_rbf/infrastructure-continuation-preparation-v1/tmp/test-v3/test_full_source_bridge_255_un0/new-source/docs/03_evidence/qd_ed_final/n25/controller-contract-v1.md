# N25 conditional CPU controller contract

Status: CPU preparation only. No adopted budget, live plan, preflight, cohort, validation or formal release is produced by this source. Science is exactly Phase A aadec3f7435f31c60b74f709efb61427c3b829c7. All new root references are external immutable artifacts; no review/proof hash is compiled into its own source manifest.

## Units, budgets and phases

The new backend check is **one health-ledger resource process, zero episode attempts**, zero model/API/simulator calls, <=60 active seconds plus <=40 cleanup seconds. Existing runner health accounting adds its measured wall time to cumulative 100 GPU hours and recovery GPU-hours; it does not increment episode/recovery-attempt counts. All reservations and failures consume this one opportunity. No second resource ID, retry, additional UUID probe, provider readiness call or historical tensor read is allowed. A cleanup failure retains measured cost as incomplete and requires reconciliation; it cannot produce a proof.

The Dev cohort independently permits 40 primary cells and <=2 exact typed recovery episodes, <=1 per scientific cell, <=42 episode dispatches. Before the resource launch, all 40 primary/2 recovery bucket slots and protected attempt reserves must fit a separate finite root budget authority. Current preparation changes no 478/100 caps. The root may later adopt a new finite attempts/baseline/development record; validation180/formal40/recovery20 and GPU hours100/protected32+12 cannot change here. No source default claims future capacity already exists.

Dev authority freezes local_gpu_hours once, after actual resource accounting: >=1840/3600 and <=min(22, remaining unprotected cumulative hours). This is a per-dispatch hard cap, not a promise that 42 worst-case durations all fit. Every dispatch must accommodate its full 1800+40 seconds locally and cumulatively. Budget exhaustion closes incomplete/INVALID with retained partial results/costs; it is not numerical rejection or permission to resume. Existing append-only protected-hour reservation records must agree with state.

## Evidence and source

All Phase A manifest files remain byte-identical except explicit runner/worker routing. The shared-route-insertions record reversibly restores exact Phase A source; function allowlists also prevent unrelated shared-function changes. The worker adds only N25 admission, same-process independent RBF auditing and receipt verification. Original N23 quality audit and all other worker functions are unchanged. Each N25 guided search requires its profile-bound gate even if all markers are deleted; controls reject activation. N24 rescue is off. Provider-only C0/Q0 serialized omission remains legal.

The independent reference is fixed in independent-arithmetic-protocol-v1.md. Native comparisons use full original dtype tensors and contiguous uint8, including signed zero, with no tolerance. It neither calls the new helper as its oracle nor asserts that CPU proves CUDA. First-guided initial + each of ten rollout first-active calls yield <=11 witnesses (20KiB numeric/call,220KiB/episode,16KiB metadata/call). Audit binds same-call origins, reset/context/phase/timestep/cost, raw input/projection/full translation gradients, original-normalization norm, operand and actual before/after addition. Zero/coincident/all-saturated gradients are valid. Later calls have scalar consistency evidence only, not an exact replay claim. Only the future metered worker reads its own native payload; supervisor consumes hashes/JSON, no unmetered CUDA audit.

No-guided metrics-file absence requires three-way explicit guided=0 (native canonical counter, episode compute, terminal). N25 additionally requires a zero-coverage independent gate. The unchanged old timeout diagnostic is retained; only its private evidence-reader wrapper handles this already-proven absence, preserves keyword defaults and binds original and wrapper source identities. No shared globals, transport gate or old N23 source is changed. Absence changing to presence rejects eligibility.

## Closed gates and outcomes

Entry requires a new root predecessor artifact proving valid aggregate N24 Dev rejection or valid aggregate validation rejection after full Dev promotion. Active/incomplete/INVALID are closed. No protected per-task results are read for N25 selection. The root predecessor wrapper binds original Dev result and a root aggregate review; it cannot rewrite prior result/status.

Root preflight source review binds final committed source, old-quality byte bridge/proof, unchanged runtime, fixed independent cases, predecessor and finite budget authority. A separately adopted resource authority binds current boot ID. Release is exact and one-shot. Native report/process/source/runtime/UUID/raw UUID type+bytes and all 12 cases must pass, with five per-case corruption controls. Actual settled health terminal is required before Dev. The final Dev source must be exactly the preflight source.

Dev is task-major tasks0..9 C0/Q0/N23/N25 using original frozen Dev seed/init metadata. Comparator cannot promote. Numeric futility is considered only after complete quadruples; promotion requires all40valid, >=5/10 and >=each control, substantive QD/ED and fixed176/11 work. No activation threshold. Sole Codex timeout classification is identical for all arms; original invalid attempts, partial token totals and all costs persist. Failed recovery or any other invalidity closes. The controller cannot restart; status/journal disagreement retains both prefixes and every cost, marks INVALID, never invents zero denominators.

## Exact external schemas and order

Disabled JSON templates under the variant's `phase-b-templates-v1/` contain required shapes with null references and `executable:false`; they are not consumable authorities. Source functions define exact schemas:

1. `contract.predecessor`: predecessor-review-v1.json; original result/ref and the real n24-root-terminal-review-v2 schema (decision=ACCEPT_TERMINAL_RECONSTRUCTION, source manifest commit/files/sha256, accepted_cells/counts/native/plan/ledger bindings). Validation case accepts only an aggregate rejection review.
2. `contract.budget_authority`: budget-adoption-v1/authority.json; schema n25-finite-budget-authority-v1, cohort_id, caps, amendment string, amendment_document ref, predecessor ref, recorded_at, authority_interpretation. Root writes state.n25_budget_authority and exact budget/reservations under owning locks.
3. `bridge.build`: source-equivalence-bridge-v1.json. Root reads final committed manifest and verifies all frozen science bytes, reverse edits, prior N23 quality proof and its settled episode ledger record.
4. `backend.source_review`: arithmetic-preflight-source-review-v1.json. `backend.authority`: arithmetic-preflight-adoption-v1/authority.json plus state.n25_arithmetic_authority; exact source/runtime/review/budget/limits/current boot and false Dev/protected flags. `arithmetic-preflight-release-v1.json` is separate.
5. Only root may run `python scripts/qd_ed_n25_backend.py --run` from integrated owning W. This freezes a resource plan and charges before one child. Successful proof is arithmetic-preflight/proof-v1.json; failed/partial artifacts remain.
6. `contract.final_review` binds actual successful proof and source/runtime/bridge/protocol/predecessor; `contract.authority` adopts the fixed local cap and state.n25_dev_authority. Root then calls `python scripts/qd_ed_n25_prepare.py --freeze --output V/plan.frozen.v1.gpu7.json`.
7. Root exact execution-release-v1.json, then `python scripts/qd_ed_n25_supervise.py --plan V/plan.frozen.v1.gpu7.json --release V/execution-release-v1.json --status V/execution/supervisor-status-v1.json`.

These are prospective activation instructions only; CPU executor neither performs them nor supplies missing actual evidence. All output/controller files stay within this variant; attempt payloads use frozen artifact_root. Validation/formal launchers are absent.
