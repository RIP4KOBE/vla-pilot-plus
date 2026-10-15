# N25 measurement summary preparation — CPU handoff

Preparation is complete; real-input reading remains disabled. All new files are under this directory. No implementation, owning worktree, research state, budget, ledger, current attempt or prior research evidence was modified or read. No Torch/runtime import, CUDA, API, model, simulator or real native payload was used.

The reader is summarize_v1.py, with guard_v1.py and normative schema-v1.md / output-schema-v1.json. It summarizes recorded N25 scalar measurements for a separately frozen list of accepted terminal cells. It never decides task efficacy, promotion or a new algorithm. Fixed initial/rollout/iteration groups retain 384-component denominators, missing measurements, native dtype norm distributions, existing audit/receipt cost consistency and bounded witness coverage. The intended update operand is explicitly not called measured output delta.

Input selection belongs to root's later read authorization. root_attestation means every listed cell is accepted, terminal and not inflight; it does not assert the whole cohort has terminated or that all cohort cells are included. This follows the latest scoped instruction to select settled N25 cells, and avoids imposing an unrequested whole-cohort gate. The frozen root manifest should state its selection rule so the subset cannot be mistaken for the scientific denominator.

## Verification

- cpu-tests-v1.log: 15 independent synthetic tests passed.
- cpu-guard-tests-v1.log: 7 tests passed. Six deliberate denied operations verify outside-scope read/write, tensor read, Torch import, socket creation and subprocess launch; zero unexpected denials or actual network/process launches.
- cpu-final-targeted-v1.log: 3 checks passed after descriptive guard labeling and counter handling.
- cpu-final-targeted-v2.log: 2 passed, 1 fixture error, retained unchanged. CLI synthetic files had populated a path that the absence fixture expected not to exist. The reader correctly rejected that mismatch.
- cpu-final-targeted-v3.log: all 3 affected binding/absence checks passed after giving that fixture an isolated synthetic path. Production absence rules were not relaxed.
- cpu-cli-v1/v2/v3.log: synthetic CLI compositions passed. The final v3 composition binds the exact final reader/guard hashes, opens four synthetic JSON files once each (25,270 bytes), opens no linked tensor, and finishes in 0.0028147209668532014 seconds with zero guard denials. Older synthetic release/result files remain historical.
- cpu-closure-v1.json records the final summary. Tests overlap; their counts should not be summed as unique cases.

The final reader and guard SHA-256s are respectively db87d122bbb133e592c853407554b796e221be165209e52a7d1509d2fc95590f and 93e1fcdde7fdc4d544d7fee3291c8b97445bdd1428e1f5078128fe7402f0ced4.

A guard wording refinement changed its reader-mode label from real_payload_reads_authorized to input_scope=exact_manifest_paths. Earlier true labels indicated exact-path reader mode, not an actual research-data read: every CLI fixture path was inside this directory. The original label source is preserved in guard-before-label-clarification.py.txt.

To reproduce the main test, copy summarize_v1.py, guard_v1.py and test_summary_v1.py into a new synthetic-only subdirectory under this preparation directory, then run the following command against the copied test file. This avoids overwriting saved test guard reports:

    CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python /absolute/new/synthetic/directory/test_summary_v1.py

## Later root-only read procedure

No real release has been created. input-manifest-template-v1.json and read-release-template-v1.json both have executable=false and real_input_authorized_now=false. Their nulls and false attestations must not be mistaken for ready evidence.

1. Independently choose and review at most 10 accepted terminated N25 Dev cells. Freeze only the four allowed JSON/JSONL roles per cell and root's exact selection/identity attestation. Do not add source/context/events/tensor/Stage/image/protected or prior-round files.
2. Review the final source/schema and freeze the completed manifest directly in this directory. Freeze a separate root read release binding the manifest SHA, reader SHA, guard SHA and an unused output filename. This is read authorization only, never dispatch or research-budget authority.
3. Execute once with CPU environment bounds, using summarize_v1.py --manifest ABSOLUTE_MANIFEST --release ABSOLUTE_RELEASE --output ABSOLUTE_NEW_OUTPUT. The three control files must be directly in this preparation directory. The independent 60-second wall timer, maximum 40 present files, 16 MiB/file and 128 MiB total apply.
4. Preserve the result or error artifact and all read counts. No automatic retry, scope enlargement or field-driven selection is provided. A failed setup before payload reads still needs root review before another release.

The summarizer checks existing hash/JSON associations only. Root's existing accepted-cell adjudication remains authoritative; no protected or task-success information is consumed. It does not reconstruct tensors, independently verify witness slot identity, infer ledger GPU seconds from the worker receipt, or pair N25 metrics with unavailable N23 raw-gradient telemetry. Real schema compatibility has only been reviewed statically and tested synthetically in this assignment. No empirical N25 mechanism conclusion is available from this preparation.
