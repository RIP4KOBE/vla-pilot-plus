# N23 conditional validation runtime contract v1

CPU preparation only. The immutable scientific protocol is the adjacent
protocol-validation-conditional-v1.md. No protected execution is enabled by
this document or a draft plan.

The source bridge retains every one of the 214 Dev fingerprints. Only exact
explicit validation routing insertions in runner and worker.validate_context
are permitted; reversing those exact insertions must restore the Dev bytes.
All science, arithmetic, provider, profile, decoder and other worker bytes
remain unchanged. Historical Dev receipts and the four-attempt arithmetic
proof are verified under their actual source, never the evaluation commit.

Root must create validation-dev-promotion-review-v1.json with schema
n23-dev-promotion-review-v1, disposition promoted, allow_validation true,
dev_plan, dev_status, dev_result hash references and the original backend_proof.
The exact actual result writer is bound in the contract. Source review schema
n23-validation-source-review-v1 binds source, source_bridge, dev_plan, protocol,
runtime, backend_proof, disposition accepted, no_execution_release true.

Private n23_validation_authorization must explicitly bind schema
n23-validation-authorization-v1, cohort_id N23_VALIDATION_20260930, seed_cohort,
protocol_sha256, dev_review, source_review, run_once true, physical_gpu 7.
This consumes existing caps only; it neither changes the Dev amendment nor
expands the old Dev recovery scope. Root chooses the first fresh complete
cohort solely through metadata under locks at freeze and release.

Freeze with qd_ed_n23_validation_prepare.py --freeze --output
<N23>/validation-plan.frozen.v1.gpu7.json. CPU preview requires
--preview-cohort c1..c4 and remains unfrozen with missing reviews.
Supervisor qd_ed_n23_validation_supervise.py requires --plan, --release,
--output-dir. Its exact release schema is n23-validation-execution-release-v1
and binds plan, source_commit, cohort_id, seed_cohort, all episode_keys, limits,
dev_review, source_review, backend_proof, physical_gpu, uuid,
validation_authorized true and formal_authorized false.

The 60 primary cells are ordered block/task/arm C0,Q0,N23. At most two
prospectively typed whole-episode recoveries are separately charged, at most
one per cell. Original terminal invalidity and unknown token costs remain.
All 60 first-valid native cells are required; no validation futility or second
cohort retry exists. Full protected detail is persisted separately from an
aggregate-only disposition. Formal dispatch remains closed.

## Continuation evidence addendum v1

Only the entry evidence changed prospectively; original protocol SHA remains
`b202e2bf03e13ea4d66fdd355f7959bbb40f264aeb3c9bd37f57959efdc63615`.
Bind addendum `validation-continuation-evidence-addendum-v1.md` SHA
`536c4508cdf21fdf59a86acdbd83ab2f8fc45b99c9e14e9b1a4bdf35329d484c`
in the source bridge, validation plan, Dev promotion review and source review
as `continuation_evidence_addendum` hash reference. Review schemas retain their
original names with this additional required key. Older prepared templates
lack this field and cannot authorize the updated implementation.

The only accepted Dev result is now `result-continuation-v1.json` /
`n23-dev-continuation-result-v1`, with exact source-bound reader
`continuation_implementation/continuation/n23_continuation_report.py` SHA
`93143e94b06802f2f681380f040b7e52b66b2c675c4fe3e3d3955fc441c0ec12`.
Its status must be `execution/supervisor-status-continuation-v1.json` /
`n23-dev-supervisor-status-continuation-v1`. All40 original scientific cells,
all charged attempts/costs, original three valid primary failures and the
unchanged metered backend proof remain required. The original failed v2
result/status are hash-verified and remain INVALID_OR_INTERRUPTED.

The new historical helper checks the separately frozen eight-file external
source at commit `dd27e77edd5e8d67aba998c1d0441c2b8e48713c`, its actual
source/authority/root-review hashes and launch witness. It reads historical
committed bytes with git show; it never invokes a current-HEAD 5110447 gate
on the later evaluation commit. The copied N7 omission adapter is exactly
the root-reviewed bytes, SHA
`fc98d401fb6095fb0a4311fa2de5e04d9940b6f5406e96078ba3b350168821c5`.
It applies only to historical Dev N7 counters. N23 checks, validation
supervisor/recovery and scientific/native arithmetic remain unchanged.

Root must first wait for an actual full continuation promotion, review this
evaluation-only source bridge, integrate it only after Dev is terminal, and
then execute the existing metadata-only freshness/full-capacity gates before
separately adopting validation authorization and release. No new backend
check or Dev consumption is permitted. CPU draft cohort labels are examples
and must never be reused as a fresh-cohort release decision.
