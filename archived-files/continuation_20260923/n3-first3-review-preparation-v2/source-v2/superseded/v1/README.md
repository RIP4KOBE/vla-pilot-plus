# N3 first-three native review tool

Preparation only: no actual N3 output has been read. Root must separately authorize the exact first-three accepted representatives after the final source/plan/report freeze. This tool never authorizes checkpoint release or dispatch.

`review_first3.py` uses the reviewed production reporter for JSON/source/compute/native-audit gates, then the frozen auditor integrity loader for only the accepted N3 episode. It compares existing native tensors only. It does not invoke provider, quality helper, projector, model, simulator, or another full audit.

## Manifest

Every reference below is `{"path": "/absolute/file", "sha256": "64 lowercase hex"}`. Root creates the actual manifest after outcomes exist:

```json
{
  "schema": "n3-first3-review-inputs-v1",
  "matrix_report": {"path": "...", "sha256": "..."},
  "matrix_report_input": {"path": "...", "sha256": "..."},
  "source_root": "...final worktree...",
  "source_commit": "...actual final source HEAD...",
  "cells": [
    {"profile": "C0", "attempt_id": "...", "references": {"terminal": {}, "audit": {}, "compute": {}, "metrics": {}}},
    {"profile": "Q0", "attempt_id": "...", "references": {"terminal": {}, "audit": {}, "compute": {}, "metrics": {}}},
    {"profile": "N3", "attempt_id": "...", "references": {"terminal": {}, "audit": {}, "compute": {}, "metrics": {}}}
  ],
  "n3_episode": {"episode_dir": ".../eds_eval/decision_evidence/episode_000", "status": {}, "index": {}}
}
```

The matrix report input already binds base and recovery plan references. Three cell refs must exactly equal its unique complete-valid representatives; no original invalid bundle is opened. Prospective C0 baseline versus Q0/N3 development resource buckets do not change the fixed Dev science identities.

## Root authorization

Required fields:

```json
{
  "schema": "n3-first3-read-authorization-v1",
  "status": "authorized",
  "freeze": {"path": ".../freeze-v1.json", "sha256": "..."},
  "manifest": {"path": ".../inputs.json", "sha256": "..."},
  "output": "...new separate review directory...",
  "reviewed_matrix_report": {"path": "...", "sha256": "..."},
  "reviewed_metadata_gate_sources": {
    "scripts/qd_ed_n3_report.py": "...final reviewed SHA...",
    "scripts/qd_ed_n3_plan.py": "...final reviewed SHA..."
  },
  "n3_audit_snapshot": {
    "audit": {"path": "...", "sha256": "..."},
    "status": {"path": "...", "sha256": "..."},
    "index": {"path": "...", "sha256": "..."},
    "auditor_sha256": "...frozen production auditor SHA...",
    "binding": "root_verified_unchanged_after_complete_frozen_audit"
  }
}
```

The snapshot is an explicit root attestation following the complete original audit. The accepted audit alone is not treated as an immutable certificate: status/index refs and every indexed bundle SHA are verified before decoding and again at exit. Metadata helper semantics must be reviewed before root supplies their hashes; their current content or agreement with a plan alone does not authorize it. Both modules and the fixed science-source list must also match the actual final plan inventory, live bytes and git objects.

## Execution after authorization only

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python review_first3.py --manifest /absolute/inputs.json --authorization /absolute/root-read-authorization.json --authorization-sha256 SHA --freeze /absolute/freeze-v1.json --output /absolute/new-output --execute-reviewed
```

Run stdout/stderr/exit metadata should be preserved outside the new output directory. A failed or incomplete read is preserved; do not repair its inputs or turn missing evidence into zero. Exit0 means the read completed, not that all checkpoint checks pass: inspect `review.json.all_checks_pass`.

Output includes all N3 guided rows and all active 11×16 canonical populations, comparator ties/transitions, 10×16 actual parent slots and native prior association, all final-pool ties, separate original outcomes, the existing eight correctness/activity checks, limits and complete input/source/bundle hashes. All-unsupported or no-history N3 remains non-qualifying; scalar changes alone cannot satisfy search activity. Actual normalized Stage input, unique insertion ancestry, hypothetical search and physical/task benefit remain unobserved.

`test_review_first3.py` uses synthetic fixtures only; its admission fixtures isolate the wrapper with mocked production metadata helpers. They do not replace the independently tested production reporter/native auditor or establish actual episode acceptance.
