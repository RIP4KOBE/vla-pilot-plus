# Arbor engineering leaf 15.2: pinned submodule source freeze

Committed CPU integration repair: `289a7dc2df93a015bd559d3bf2eba962054ccdb7`, parent `79f7cd2790cc667726a7cbe872a0a7f349a0e5b4`, branch `exp/n32-archive-eligible-cpu-20261004`. Working tree is clean. No scientific score or success is claimed.

## Implementation and compatibility

Only `scripts/qd_ed_n23_worker.py` and `tests/test_n32_submodule_freeze.py` changed. The single explicit cross-gitlink allowlist entry is `third_party/rdt/scripts/maniskill_model.py`. The frozen superproject commit identifies its gitlink commit; that exact commit must exist as a commit object in the local common Git directory's `modules/third_party/rdt` database. The pinned tree must contain a regular blob, and the repository-local regular-file bytes must equal it. Submodule HEAD and adjacent worktree bytes are never source inputs. Object replacement is disabled and lazy fetching is disabled. Missing objects fail closed.

The existing record format remains `commit/files/sha256` with `path/sha256` rows. The superproject commit transitively binds the gitlink and blob; no mutable HEAD field or new optional provenance field weakens equality. `verify_source` still regenerates and compares the entire record. Root must be the Git top-level directory; canonical relative paths and every path component are checked against symlinks. As before, identical committed checkouts can share a content record: execution root binding remains enforced by the unchanged release/context checks and `attest_loaded`.

Reviewed all 61 caller files / 125 call sites captured in `caller-inventory-v1.json`, including internal worker calls and focused tests. Prepare/backend/contract paths supply explicit inventories, bridge/preflight/release paths verify complete records, and worker contexts reconstruct records. No signature or schema migration is needed. Historical reverse-source allowlists remain unchanged and are not silently reapproved by this repair. N32 inventory completeness and unknown/adjacent loaded-module rejection are unchanged. Science, thresholds, attestation scope, and accounting are untouched.

## Pinned materialization

Superproject parent pins RDT `b896f4dcac8ed1c3fae4a056200db267607f131f`; blob `c8baddb41b5b2a838550ad6d45560de1b4270045`, SHA-256 `503644ff977704f212e007bc6cd05e4ea7ce84c66324bc31eccf36da31555bb0`, 11614 bytes. `materialize-v1.py` used read-only local Git object commands and an exclusive regular-file write inside this worktree. It created no `.git` pointer, ran no submodule checkout/init, and changed no gitlink or shared administrative files. Exact commands, paths, object IDs and before/after shared administration hashes are in `materialization-v1.json`. Only the required file was materialized.

## CPU validation

CUDA was hidden and numerical thread counts limited to two. No GPU, provider, model or simulator calls occurred. Test temporary repositories are contained in this report directory.

- Initial focused run: 29 passed, one fixture setup error because materialization had not yet occurred; retained in `tests-v1.log`.
- Final focused run: 33 passed, 55 deselected, exit 0 (`tests-v2.json` and `tests-v2.log`). Covers pinned bytes despite unrelated database HEAD, linked worktrees, missing/modified/wrong-pin files, missing database/objects, invalid pin object type, wrong root, file/parent/committed symlinks, unknown sources, record/hash/commit tampering, changed gitlink, and compatible regular files. Existing real closure and loaded-source rejection tests passed. One existing invalid-escape SyntaxWarning in `core/fkd_class.py` remains.
- Post-commit complete real inventory: 549 files; `source_record` and strict `verify_source` passed. Digest `78d689a516a3f093857f2c0080813a924aaee13f117d23d292fd80c5124bf6c3`. Six actually loaded repository modules also passed unchanged attestation. An import guard rejected model/simulator imports; none occurred. Exact record, command, environment and outputs are in `source-record-v1.json`, `roundtrip-v1.json`, and `roundtrip-result-v1.json`.
- `git diff --check` passed; only the two intended source/test paths were committed. Parent, clean status, unchanged gitlink and shared administration were checked after the roundtrip.

## Remaining prerequisites

- Root review/adoption of commit 289a7dc2df93a015bd559d3bf2eba962054ccdb7 and pinned materialization provenance is still required; no owning source has been adopted.
- Future execution checkout must contain the pinned local RDT objects and regular source files. This repair materialized only scripts/maniskill_model.py; the remainder of RDT (models, configs, etc.) is absent here and full model/runtime readiness was not tested.
- Create and validate a fresh prospective runtime/manifest binding in the intended execution checkout under separate authorization, with a distinct cohort/attempt identity. No release or prospective launch manifest was generated in this leaf.
- Before any GPU cohort, obtain separate accounting amendment, root review and source/release freeze. Preserve terminal invalid n32_dev_t00_c0_20261004 and its 706.4010170580586 seconds / 0.19622250473834962 GPUh unchanged.

No release generation, launch, owning tree/ledger mutation, source adoption, new agents, protected evaluation or scientific evaluation occurred. The old invalid attempt and its charge remain immutable.

Applied skills: [Arbor entrypoint](/home/hynx/.codex/skills/arbor-research-agent/SKILL.md), [orchestrator](/home/hynx/.codex/skills/arbor-agent-orchestrator/SKILL.md), [executor](/home/hynx/.codex/skills/arbor-agent-executor/SKILL.md). User restrictions govern this continuation; no coordinator/tree updates or new agents were used.
