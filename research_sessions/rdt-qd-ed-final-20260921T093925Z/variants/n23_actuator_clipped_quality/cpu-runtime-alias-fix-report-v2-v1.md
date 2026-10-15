# N23 v2 runtime alias closure correction

Final isolated source commit: `77302aab40d6b059e85c8d1d8011ea36cb3d3856`, immediately after8aa0ba8. Source is frozen and clean. The patch touches only `scripts/qd_ed_n23_v2_contract.py` and `tests/test_qd_ed_n23_v2.py`; no frozen runtime, v1/global verifier, scientific code, profile, provider or controller is modified.

Root's actual owning-runtime check found the frozen lexical worktree prefix was omitted from N23 admission's allowed roots, despite resolving to the same canonical owning worktree. This executor did not read actual runtime input contents. Root independently reports all3291 frozen runtime files pass the existing strict verifier with both proven-equivalent root prefixes.

The new v2 validate_runtime first requires `Path(runtime['worktree']).resolve() == Path(root).resolve()`. It calls the original v1 runtime validator with a local copy of the runner-function mapping, wrapping only verify_files to append that exact lexical prefix. Every existing runtime equality, Stage/GPU/EGL/probe/engineering check still executes. The original verify_files still checks allowed lexical prefix, owned resolved target, frozen resolved_path/link_target, existence, SHA and size. The original function mapping is never mutated.

Focused verification passed **31 tests,164 deselected in2.03 seconds**, including the previous failure reproduced by unchanged v1, legal compatibility symlink accepted by v2, wrong resolved root, truly escaping symlink target even with matching bytes, changed bytes, wrong frozen resolved_path and wrong link_target rejected. Existing runtime/profile/source closure cases are included. The same historical-data path guard reports zero blocked reads and CUDA uninitialized. No unaffected large suite was repeated. Log: `cpu-v2-runtime-alias-v1.log`.

Reproduce from implementation:

```
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_v2.py -k 'runtime or closed_matrix' --basetemp=../n23-v2-guarded-fixtures-runtime-alias-review-new
```

New complete source manifest `source-manifest-v2-cpu-final-v2.json` still has205 records. File SHA256: `15e055107bac9961b3d92f80959daba2f69c4155b07612e59b879768dda81874`; canonical source SHA: `3315cf8aacda95fc44a869109fb8bcad6e4b0d857c1ac723c4389bcd8201704f`. `cpu-v2-source-closure-v2.log` verifies committed bytes, permitted changed-path scope, zero blocked reads and CUDA false. Earlier manifests/reports remain intact.

New non-executable drafts are `plan.cpu-draft.v2.final-v2.json` (SHA `adcfd5d675c1558a4142a1c04c54a4bef9811fa2baabd7b5254ac876ce81cf95`) and `backend-plan.cpu-draft.v2.final-v2.json` (SHA `01e615670eb25e96f46ee5e1bafbfbc06f213ccb9247c8855ad87230711bfcde`). They retain missing reviews/proof and missing backend corpus. These are preparation artifacts, not authority to launch.

Root may now fast-forward owning source to the exact new commit, regenerate the owning source record/plans, independently check the actual runtime, then proceed through the unchanged external review/adoption/preflight gates. No source change after the one preflight is permitted. Recovery/predecessor helper bytes remain unchanged, so the existing actual named-timeout diagnostic proof is unaffected. No actual GPU/provider/simulator/model/state/ledger/lock/Arbor operation occurred in this correction.
