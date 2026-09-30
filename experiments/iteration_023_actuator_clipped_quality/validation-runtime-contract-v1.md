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
