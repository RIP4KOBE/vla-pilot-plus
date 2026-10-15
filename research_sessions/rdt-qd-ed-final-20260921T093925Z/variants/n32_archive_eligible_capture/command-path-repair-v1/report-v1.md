# Node15.2 CPU implementation executor report v1

Engineering preparation complete; production adoption pending. Research goal remains unmet. No score or scientific improvement is claimed.

Source commit: `04d1255016fa13a2d467995b9e37a6a829356a1c` (base `36aac818c8ea0ec3ce18413e678963818bb5bb5d`).

## Exact changed files

- `scripts/qd_ed_n32r3_bridge.py`
- `scripts/qd_ed_n32r3_contract.py`
- `scripts/qd_ed_n32r3_paths.py`
- `tests/test_n32r3_paths.py`

## Implementation

Optional `plan.command_path_amendment` is a hash-bound reference to a separately versioned `n32r3-command-path-amendment-v1` evidence document. Unamended plans retain their original commitment shape and exact command behavior. The new validator re-enters the unchanged history mapping validator, including hardcoded original preparation review digest `8666822f801c4e04aece1e7e9bb48c245ec206e69a8d73f8821a9022fbc91428`. Original command_candidates and carry_forward_map references remain unchanged.

It validates exactly16 ordered unique cells, each original old_argv/parent manifest and original exact_changes, original row/source/runtime bindings, and owning runtime/artifact containment. Every amended pair is derived by resolving only hydra.run.dir, main.eds_eval.output_dir and main.eds_mechanism_pretest.output_dir. The output must remain the same anchored attempts/<episode_key> destination with eds_eval and mechanism children. Exactly those three tokens must change. The amendment document must equal that complete derivation, and actual builder argv/output must then equal the amended pair exactly. No general command canonicalization is introduced.

The optional amendment reference enters continuation commitments, so existing exact comparisons bind it through manifests, detached root reviews/releases, contexts, native receipts, terminal receipts and lifecycle records. No history validator, scientific source, native/generic audit or shared runner was edited. Source continuity remains independently required.

## Evidence

- Initial focused run: 39 passed in 4.21s.
- Final focused run: 156 passed in 7.66s across test_n32r3_paths.py, test_n32r3_source.py, test_n32r3_continuation.py and test_n32r3_execution.py. Exact commands and results are in cpu-evidence-v1.json.
- Real read-only metadata verification passed the unchanged original review/map and all16 original parent command anchors. With the disabled candidate attached only to an in-memory copy, the actual builder matched all16 amended commands exactly. Per-cell argv hashes and outputs are recorded in cpu-evidence-v1.json.
- Negative coverage includes non-path parameters, runtime/scientific binding changes, arbitrary/equivalent lexical output substitutions, wrong roots, dropped/duplicate/reordered cells, altered original argv/parent/delta/map/review anchors, stale hashes, and omitted amendment commitments in manifests, detached release or root review.
- Existing historical receipt tamper and source/native audit regression tests passed. Synthetic lifecycle tests write only temporary fixtures inside this isolated worktree; those newly created temporary directories were removed after testing.
- git diff --check passed; commit contains only the four allowed files and the implementation worktree is clean.

## Disabled candidate and limitations

`command-path-amendment.CANDIDATE-v1.json` binds the actual owning paths and original references and has release_enabled:false. It is evidence, not an executable release or root approval. No production source continuity approval, manifest composition or full production release validation was performed. No GPU dispatch, external model/provider call, credential access, scientific evaluation, protected validation/formal result access, state/checkpoint/ledger mutation, old artifact edit/deletion or lock operation was performed. No additional agents were used. Existing driver retains lock ownership.

No implementation blocker remains from the diagnosed path mismatch in this CPU check. Independent root source/adoption review, new manifests/release, full validation and fresh resource admission remain outstanding. STOP was absent at the recorded checks and work completed within the 1800-second bound.

## Precise next root steps

1. Independently review source commit 04d1255016fa13a2d467995b9e37a6a829356a1c and the disabled command-path-amendment.CANDIDATE-v1.json. Retain the rejected v1 release and every original preparation/history artifact unchanged.

2. Adopt the operational commit into the owning worktree only after root review. Create a new source inventory and separately approved source-continuity review for that commit, including the new paths module and test. Preserve scientific source 1065f38122379a515b60a9a424f574330405b66f and the existing exact shared-runner delta.

3. Create a separately versioned disabled composition input using the original carry_forward_map, command_candidates and preparation_review references. Add command_path_amendment as the candidate path/sha256 reference. Preserve its owning worktree/artifact_root/runtime bindings; do not change the candidate release_enabled:false evidence flag. Explicit root adoption occurs in the new plan/review/release commitments.

4. Revalidate the original anchor/map and amendment on the owning filesystem, then use scripts.qd_ed_n32r3_prepare to compose all16 fresh manifests into a new owned destination. New manifests must commit the amendment reference and newly composed config hashes; do not reuse rejected manifests.

5. Create a new frozen plan with the fresh manifest index, then independent root production review and detached release whose continuation includes the exact command_path_amendment reference. Run full validate_release with the externally supplied release digest; CPU command matching in this report is not production release validation.

6. Only the production root/driver may adopt after full validation and perform fresh STOP/deadline/resource/budget/private-GPU admission under existing authority. Preserve all14 historical receipts, the old invalid charge and all scientific/native audit gates. Do not dispatch from the rejected v1 release.

