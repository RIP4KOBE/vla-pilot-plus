# Node 15.6 independent CPU composition review

**B2: supported for prospective source freeze. B4: passive CPU composition supported; full execution evidence remains blocked. B5: hard rejected.** Engineering review only; score `null`, target_met `false`, release disabled. No approval/admission token or source adoption.

Isolated source: `b1d20fc0481721da6ebaab161c5a2ef7c3d50173` (clean). Owner source: `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`. Production inventory: **1,086** entries, canonical SHA-256 `5b6ee87a52d7db339f98e04b78232356b5db0b99eb22673dfa6907a04bd35a0a`. Launcher SHA-256 `86ecaf3d0d1454613ee4bec1337dca7ed81d35ce59cfda1e62d7839a58e39b82` was checked without execution.

The bounded independent checks passed:

- Current source bytes match committed Git blobs and pinned dependencies; source/scientific_source match across all arms.
- All **40** production manifests regenerate exactly. Task/seed/profile rows, argv, complete composed configs, resolved configs and disabled contexts join correctly. Old/new science differs only by exact output-path/source-commit substitutions. Every prospective output is absent, including broken symlinks.
- **3,291** runtime files, **3,000** relocated asset records and **6,758** closure entries verify. Interpreter/distribution/generated/_cyutility rules are preserved. Runtime changes are confined to checkout relocation, preparation history and the isolated LIBERO config binding. Native manifest and protocol/accounting references remain unchanged.
- **107** indexed artifacts were hash-checked. Actual preparation, namespace repair, full-config comparison and production verification logic were inspected, including the two retained failed diagnostics. Preparation was not restarted.

Limits and concrete findings:

1. Eight passive import resolutions reproduce; prior actual CPU imports cover four named modules/namespaces. An adjacent-checkout path remains in the recorded search path, although sampled origins select the isolated tree. This does not establish exhaustive worker provenance.
2. Historical readiness booleans and inherited controller `ROOT_REVIEWED` do not establish current readiness or external approval. Controller source bytes match; no deployed instance or physical-gain claim is established.
3. Immutable production runtime observations and complete process-bound worker before/after receipts remain absent. Multi-GB checkpoint/native-library bytes were not rehashed here; their preparation verification logic/evidence and unchanged manifest bindings were reviewed.
4. Production `validate_plan` rejects the exact draft with `N36R2 draft only; release disabled`. All 40 contexts have `release: null`; authority/root_review/execution_release remain null.

Next steps are separate owner adoption consideration, separately authorized complete worker/runtime evidence, and separately reviewed B5 protocol/admission/accounting/resource routing with external root approval and detached release. This report authorizes none of them. Retained 504 attempts and 75.49265038509455 GPUh are inherited, not recalculated.

Checks used 33.475s wall time (main check 33.269s CPU), two-CPU affinity/thread limits, under the 120s check cap. Review elapsed 300.6s of 900s. Both STOP paths were absent before final writing; deadline `2026-10-11T11:13:13Z` remains unchanged. No source, owner state, ledger, lock/driver or old-artifact writes.

[Machine-readable report](report-v1.json) contains exact hashes, code locations, narrow verdicts and all check results. [Independent check evidence](check-results-v1.json); [supplemental bindings](supplemental-bindings-v1.json).
