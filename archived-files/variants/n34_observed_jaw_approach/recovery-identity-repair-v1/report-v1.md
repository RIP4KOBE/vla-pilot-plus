# Arbor node15.4 — N34R1 identity/accounting repair

Status: CPU_IMPLEMENTATION_COMPLETE_NOT_GPU_RELEASE

Source commit: `908efa454450a079c5ed6a1b10eff1eb9ef290c1` on `codex/n34-production-integration`.
Base executor source: `83b4ceba312835410200713e3d65a03de89f0931`; adopted owning source supplied by authority: `2d61cff3f4f0530e89294567586569e2b3bbfd72`.

Implemented the strict prospective cohort `N34R1_OBSERVED_JAW_APPROACH_DEV_20261008`: 30 fresh task-major C0/Q0/N34 identities, identical tasks/seeds/scientific configuration, and exact 9 baseline / 20 development / 1 recovery charges. Only `n34r1_dev_t00_c0_20261008` replaces `n34_dev_t00_c0_20261008`. Its row contains `replacement` with the fixed old/new identities, recovery bucket, `automatic: false`, and the terminal-closure reference/hash from authority-v1.json. Other rows contain `replacement: null`.

Manifests already embed the exact row; draft and released plans must equal this matrix. The runner persists replacement provenance at reservation, dispatch and terminal. Reconciliation and terminal verification enforce bucket/provenance, reject identity reuse, arbitrary retry/recovery pointers and duplicate/noncontiguous outcomes. Admission requires the old invalid charged group, explicit root authority, the next fresh row and exact cohort bucket ceilings. Generic global accounting retains all old charges. Historical N34 resource preparation remains globally charged; N34R1 preparation is charged against the new 5-hour ceiling using the new cohort or `n34r1_resource_preparation_v1` kind.

The shared runtime-input gate has a narrow exact-N34R1 recovery exception and retains subsequent frozen task/seed checks. Private caps remain exactly 1800 attempts / 224 GPU hours and 400/1120/180/40/60 bucket caps with 32/12 protected GPU hours. Zero automatic recoveries, complete-valid-triple futility, all-30-valid promotion, N34 >=5 and >= both controls, deadline, and validation/formal exclusion are unchanged. No model, algorithm, threshold, N31, or scientific-source file changed.

Validation: 127 selected tests passed, followed by 44 passing final recovery tests (128 distinct passing cases across these runs). The additional final case admits all 30 cells in order and rejects further admission. `git diff --check` passed. Exact commands, preserved logs and hashes are in implementation-result-v1.json. The initial run had 49 passes and one stale fixture assertion; that assertion was corrected. No broad provenance rerun was performed.

Root adoption requirements: inspect/adopt source, verify actual immutable ledger prefixes and old terminal closure, regenerate the detached source/runtime/manifest/plan/protocol closure, and put the exact contract `REPLACEMENT` object in the root budget authority's `prospective_recovery` field. Detached root review and release must bind that authority and the new plan. These implementation artifacts confer no GPU admission.

Limitations:

- CPU synthetic evidence only; no model/provider experiment, GPU job, scientific outcome, or performance claim.
- No operational APPROVED release generated. Existing release-boundary tests create explicitly synthetic approval-shaped fixtures only under the authorized output tmp directory.
- No owning state, ledger, coordinator lock, old release, protected guidance document, or protected result was read or modified; authority-v1.json supplied the pinned closure reference.
- Actual terminal closure bytes and live owning balances were not inspected. Production release verification must hash-check the pinned closure; admission must find the old invalid charged journal group.
- Strict new-source contract rejects historical N34 plans; historical source remains in git. Root must review/adopt this commit and regenerate detached runtime/source/manifests/plan/protocol/authority/review/release closure.
- Broad provenance/native audit suites were not rerun. Existing source/runtime/manifest/native validation paths are retained; focused composition, shared runtime-input, lifecycle, and release-boundary tests were exercised.
- The initial test run exposed one stale fixture assertion, corrected and covered by passing subsequent runs. Three pre-existing core/fkd_class.py invalid-escape SyntaxWarnings remain.

Scientific score: unknown; engineering-only repair. Old timeout success and telemetry remain unknown. Existing worktree and all output artifacts are preserved; no coordinator updates were performed.
