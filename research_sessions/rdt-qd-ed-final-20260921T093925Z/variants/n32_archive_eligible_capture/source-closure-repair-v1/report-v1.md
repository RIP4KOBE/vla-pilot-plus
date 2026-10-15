# Bounded CPU source-closure repair v1

Status: inventory repair committed; CPU regression checks pass; prospective freeze integration remains blocked. No scientific/task-success claim, release generation, or launch.

Parent: `c427e7acdef0a42fa56c53460dd8587ca3489b1d`  
Commit: `79f7cd2790cc667726a7cbe872a0a7f349a0e5b4`  
Branch: `exp/n32-archive-eligible-cpu-20261004`

## Repair and review

`source_paths` now explicitly requires `third_party/rdt/scripts/maniskill_model.py`, even when the RDT submodule is uninitialized. `RDTSteer.from_pretrained` prepends `third_party/rdt` to `sys.path` and imports this file as `scripts.maniskill_model`, inside the existing attestation scope. A glob would silently omit it in this worktree.

A source-only AST traversal from real `main.py` followed 65 local module names, including conditional and relative imports and package initializers. The only missing path under the current `core.*`, `scripts.*`, `utils.*` attestation scope was this RDT file. Its transitive RDT dependencies are `configs/state_vec.py`, `models/rdt_runner.py`, `models/hub_mixin.py`, `models/rdt/model.py`, `models/rdt/blocks.py`, `models/multimodal_encoder/t5_encoder.py`, and `models/multimodal_encoder/siglip_encoder.py`. Those names fall outside the current attestor prefixes; this repair does not expand or weaken that scope. Static traversal does not certify dynamic imports, runtime path precedence, or site packages.

RDT source was read without import from locally available Git objects pinned by superproject gitlink `b896f4dcac8ed1c3fae4a056200db267607f131f`. No submodule checkout, fetch, or owning-source modification was performed. Tests require that pinned local object database.

`attest_loaded` is unchanged (AST equality against the parent is tested). Audits, science, thresholds, worker behavior and accounting logic are unchanged.

## Validation

Command: `python -m pytest -p no:cacheprovider -v -s tests/test_n32_source_closure.py`  
Exit: 0; **10 passed**, 1 existing invalid-escape SyntaxWarning from statically parsing `core/fkd_class.py`; 3.02 seconds subprocess wall time. CUDA was hidden; OMP, MKL, OpenBLAS and NumExpr thread limits were 2; bytecode writing disabled. Model/Main/simulator code was parsed, not imported or executed. No broad unrelated suites ran.

The tests execute the parent's exact inventory function to reproduce the missing-module rejection, accept correctly hashed representative new loaded-module records, and reject omitted, modified, wrong-hash, unknown and wrong-root sources. They verify the real static closure and unchanged strict attestor. Synthetic attestation success is not a complete prospective source freeze or episode result.

`git diff --check`: exit 0. Commit: exit 0. Post-commit `git status --short`: exit 0, empty.

## Concrete integration blockers

The required RDT file is the sole missing regular file in the new inventory here. `source_record(REQUIRED_SOURCE | {RDT source})` raises `ValueError: source path missing or linked`. Independently, `git show HEAD:third_party/rdt/scripts/maniskill_model.py` exits 128 because RDT is a gitlink, not a superproject tree. Merely initializing the submodule will not fix that verifier limitation. The explicit inventory entry makes this fail before launch instead of silently deferring discovery to post-main attestation. Existing fixtures that directly hash every inventory path also need a materialized pinned RDT source.

1. Root review and adoption of this inventory-only repair; no release or launch is authorized by this result.
2. Separately reviewed submodule-aware prospective freeze: bind the superproject gitlink to the pinned RDT commit, verify repository-local regular-file bytes against that commit, and retain strict drift/wrong-root rejection. Existing qd_ed_n23_worker.source_record uses git show <superproject-commit>:<path>, which cannot traverse a gitlink.
3. Materialize the pinned RDT source in the future isolated execution checkout. The implementation worktree currently has an empty third_party/rdt directory; do not use adjacent checkout module origins.
4. After the above integration work, validate a complete committed source record and prospective manifest using CPU checks before root adoption/release. This task tested representative frozen records, not a release-ready full source_record.
5. Any future execution requires a distinct prospective identity, new source/release binding, and an accounting amendment preserving the old terminal invalid attempt and its 706.4010170580586 seconds / 0.19622250473834962 GPU-hour charge. Never replay or relabel n32_dev_t00_c0_20261004.

## Preservation

Read `scope-v1.md` and `../root-invalid-terminal-review-v1.json`. No filesystem AGENTS.md was found in the worktree ancestor chain or within the worktree; supplied user policy was followed. No skills, agents, providers, credentials/Poe, GPU/cloud, driver/leases, protected validation/formal results, or prohibited untracked design document were used. No owning state/tree/ledgers/source or historical attempt records were edited. The old attempt remains terminal INVALID_STOP and charged; no replay or relabel occurred. The reviewed snapshot remains accepted_cells=0, success=null, dispatched=422, invalid=18, running=0, GPU hours=56.607274131677656. These are quoted review values, not newly measured state.

## Changed implementation paths and SHA-256

- `scripts/qd_ed_n32_bridge.py`: `e142a4c579a62223c3c84df3ad5a6c786847bbd0c1a0ad63e9c88a8d7e3145d5`
- `tests/test_n32_source_closure.py`: `e5d33eff8adb9b89f48f766169a9cd717065312e713ceb5a0c5af085128f8660`

## Logs and SHA-256

- `tests-v1.log`: `3d70390be43880b289ee918c91a9491b952d1ac32bf01112ec0a011467c87d2b`
- `test-command-v1.json`: `9d7ae7ffbf4d95494a465d1c752c36b5f237d8c3902c902b16ea736a54a09cb7`
- `integration-checks-v1.json`: `50160779260da1bb11dc45fba9a6aadf5bbe6d47322bd276069dc70b0b70e7fe`
- `commit-commands-v1.json`: `a51b96139c5d929f553a3aaaa195f47e0a6b4cefd93dc9f3530e8909de36ebde`
