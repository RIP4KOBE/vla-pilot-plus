# Leaf 15.6 — bounded CPU source/runtime preparation

B2: **PASS for prospective CPU source freeze**. B4: **CPU composition complete; execution gates remain blocked**. B5: **hard rejected**. Score: null. Production accepted: false. Release enabled: false.

Source remains `b1d20fc0481721da6ebaab161c5a2ef7c3d50173`; owner remains `ca4e6a96d049c7ebb1f302d755883388ddbfdbd8`. Checkout is clean. No production source edits or new commit; no source adoption, owner-state or ledger writes. Independent review of the new artifacts is required.

- Git-verified complete source/scientific_source: 1086 identical entries across all arms, including ordinary tracked launcher SHA-256 `86ecaf3d0d1454613ee4bec1337dca7ed81d35ce59cfda1e62d7839a58e39b82`. Launcher never executed.
- Production `prepare`, `verify_sources`, runtime closure, controller semantics, runtime-file/input validators, and all 40 `verify_manifest` calls passed. Full checkpoint bytes were checked.
- 3,000 relocated asset records checked; 148 missing non-source files copied and 12 original relative non-source symlinks preserved. No owner-source-tree symlink. LIBERO config and dependency import paths bind the isolated checkout. All 6,758 ordinary runtime entries and interpreter/distribution/generated/native/_cyutility rules retained.
- All 40 Dev rows, seeds, profiles, argv and full configurations match the authorized prior drafts after only exact output-prefix/source-commit normalization. All prospective outputs remain absent. Forty disabled contexts have `release: null`.
- Actual bounded CPU imports and passive dependency origins checked. These are **not** immutable production runtime observations or complete before/after worker receipts. Controller review status is inherited source-semantic evidence, not new root approval. Device/provider fields remain historical metadata.

Two failed local diagnostic attempts are retained: an overly broad Main filename guard rejected `unittest/main.py`; the final origin diagnostic assumed namespace packages have `__file__`. Exact-path guarding and a separate namespace-aware origin diagnostic resolved these without modifying production code or rerunning completed broad validation.

Measured validation-script wall time: 163.71s / 360s; two-CPU affinity and two-thread limits. Both canonical STOP entries remain absent; deadline unchanged. Retained accounting remains 504 attempts and 75.49265038509455 GPUh, including invalid charges 86.40354533703066s and 809.4826372319367s; inherited only, no ledger recomputation.

Artifacts: [complete disabled plan](plan.complete-disabled-v1.json), [source](source.complete-v1.json), [runtime](runtime.isolated.draft-v1.json), [all40 joins](all40-joins-v1.json), [full science comparison](full-scientific-config-comparison-v1.json), [CPU origins](import-origins-v1.json), [hashed evidence index](evidence-index-v1.json). Exact commands, exit codes and log hashes are in [report-v1.json](report-v1.json).

Remaining: independent artifact review/root adoption, separately authorized immutable runtime observations and complete process-bound worker receipts, and B5 admission/accounting/resource authority with external root approval. No release or admission token was created.
