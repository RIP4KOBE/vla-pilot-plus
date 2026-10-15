# N26 existing scalar summary: finite metadata contract

CPU preparation only. Actual reading requires a separately root-authorized manifest after the immutable terminal reconstruction is independently accepted. No source integration, experiment retry, algorithm selection or GPU release is implied.

The input envelope is `n26-scalar-summary-input-v1` with `root_authorized: true`, `executable: true`, `refs`, `files`, and ordered `metrics`. The supplied template has both booleans false and unresolved refs, so it cannot execute.

Exactly five control JSON files are required:

| Role | Binding |
|---|---|
| terminal_review | Accepted `n26-root-terminal-review-v1` produced by the reviewed independent reader |
| result | Its immutable `n26-dev-cohort-result-v1`, including all accepted cells and attempt costs |
| plan | The exact ordered 40-cell plan referenced by both review and result |
| source | The original 315-file manifest with commit `6026794cd5d52f3a5054bf2704ebb3c516f9f47e` |
| terminal_input | The exact input manifest referenced by the accepted independent review |

Each ref is `{path,sha256}`. `metrics` is an ordered list of `{attempt_id,ref}` covering **every accepted N25/N26 first-valid cell**, in original plan order, including valid task failures and zero-guided episodes. There is no success, activation, gradient-size, Stage or task filter. At most 20 metric refs are possible. Original control-arm records remain in the closed result for prefix consistency; their metric files are not read.

For each selected cell, the tool binds its attempt ID and original accepted audit/context/receipt/terminal refs to the accepted terminal-input inventory, then requires its metric declaration to match exactly. No receipt body is read. A metric absence is accepted only when the original inventory declares it absent and the already accepted attempt's measured guided count is zero. Its path must still be absent. Missing positive-guided metrics, changed hashes/presence, extra files, omitted cells or duplicate calls fail closed.

Each `files` entry is exactly `{role,path,present,sha256,bytes}`. There are at most 20 metric files plus the five control files (under the protocol's 32-file ceiling). A present file is at most 16 MiB; the CLI includes the input-manifest bytes in a 128 MiB total cap. Size is checked before allocation, reads are bounded and cached once, hashes are verified, aliases/leaf symlinks/duplicate JSON keys/nonfinite JSON are rejected. Absent metrics use `sha256: null`, `present: false`, `bytes: 0`. No recursive path discovery or nested-reference following is performed. Raw Stage/native event files, tensor/image files, protected paths and full private journals are forbidden.

The two static dependencies are exactly the previously accepted `bounded_metadata_v1.py` and `metadata_semantics_v1.py` in the sibling terminal preparation directory, SHA-bound in the summarizer. Only their verified source bytes are compiled into ordinary modules; no import cache discovery, source transformation or production globals replacement occurs. `metadata_semantics_v1.calls` supplies the existing scalar-shape/phase/schedule/provenance checks. Aggregation is independent and has hand-calculated synthetic expectations. The original terminal reconstruct, native auditor, report writer and outcome validator are never invoked.

## Output and interpretation

`n26-existing-scalar-summary-v1` preserves the original `cohort_disposition`, original accepted-prefix count, planned count, and `describes_partial_prefix_only`. An accepted reconstruction of an INVALID experiment remains INVALID. The output does not report a new success rate or certify experiment completeness.

For each arm and accepted task, initial/rollout phase groups report guided decisions, call/component denominators (384 translation components per call), clipped/boundary/interior totals and ratios, zero-gradient counts/ratios, dtype and recorded stride categories, and count/min/median/mean/max of the four native scalar norm fields. Per-decision phase ratios are retained alongside pooled call statistics. Empty groups have count zero with null unobserved ratios/norm statistics. Recorded input stride is metadata, not a native replay or observation of storage offset.

Paired differences are N26 minus N25 only for shared accepted task IDs, separately by phase. Both call/component denominators are displayed; unequal call counts remain unequal. If either phase has no calls, its paired statistics are null. Unmatched tasks remain listed. No p-values, confidence intervals or same-state causal interpretation are produced.

`update_operand` means the recorded addition operand. It is not measured BF16 output delta, scheduler action change, actuator displacement or physical progress. States and Stage durations differ between arms. First-guided witnesses are not reread; zero gradients can be legal, and activity is not efficacy. The tool never chooses a successor or creates GPU/validation/formal authority.

## Future root-only execution

After separate input-scope approval, run once with two CPU threads and CUDA invisible, at most 60 seconds (the CLI arms a 60-second alarm). The output must be a new file directly inside this preparation directory. Preserve the log on any failure; no automatic reread/retry is provided.

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python /ABS/N26/measurement-summary-preparation-v1/scalar_summary_v1.py --input /ABS/ROOT_AUTHORIZED_SUMMARY_INPUT.json --output /ABS/N26/measurement-summary-preparation-v1/summary-v1.json
```

Original same-process audit, terminal review and inventory completeness remain explicit provenance dependencies. This tool checks visible scalar consistency and associations; it does not recertify unobserved tensors, Stage outputs, physical effects, resource cleanup or downstream budgets.
