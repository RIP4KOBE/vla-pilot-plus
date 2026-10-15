# N34 / Arbor 15.4 CPU implementation report

**Result: CPU implementation and independent native audit ready for root integration.**
Commit: `a4edcfd650f94d5e40ab437c46d591058ccb6e73` on
`exp/n34-observed-jaw-approach-20261008`, based on
`04d1255016fa13a2d467995b9e37a6a829356a1c`. Working tree is clean.

## Idea and changes

Implemented the registered observed jaw approach as the separate opt-in N34
profile `observed_jaw_approach_v1`. Each ordinary QD iteration can replace only
slot 15 with a competitor built from the current archive global best's canonical
plan. Outside the unchanged literal observed N31 prism, the first eight actions
are constant clipped jaw-center translations, zero rotational increments, and
open gripper. Actual observed entry produces immediate close-and-dwell: all
eight translations/rotations zero, gripper +1. No predicted-entry closure,
cross-decision memory, score bonus, forced selection, threshold changes or
simulator ground-truth target was added.

The production encoder/decoder mapping is explicitly tested in FP32/BF16:
translation 39:42, rotation increments 42:45, binary gripper 10. These are direct
normalized LIBERO commands, not absolute-orientation channels. Unrelated first8
channels and all suffix entries retain their native bytes.

N31's decision-local canonical cache/template checks and insertion boundary are
reused. N34 configuration, runtime binding, event prefix, scalar schema and audit
gate are distinct. Existing N31/N32 audits/controllers are unchanged. The new
independent audit reconstructs geometry/native writes, verifies ordinary archive
retention/selection, and binds observations through proposed/scored/selected/
decoded/committed/executed lineage to an external config/source manifest.

## Validation and CPU evidence

All commands used the existing `/home/hynx/miniconda3/envs/vla-pilot/bin/python`
with `CUDA_VISIBLE_DEVICES=` and one OMP/MKL thread. No packages were installed.
All fixtures are synthetic CPU model/environment services; no provider or GPU
experiment was called.

- `n31-regression.log`: 37 existing N31 integration tests passed.
- `n34-tests.log`: initial 52 N34 cases passed.
- `native-tests.log`: 122 cases passed (expanded N34, existing N32 runtime-native,
  and production converter tests; overlapping with the other runs).
- `n34-final-tests.log` / `n34-junit.xml`: 78 N34 cases passed, including exact
  authorized-base method parity for C0/Q0/N31/N32 in both dtypes. All 11 canonical
  populations, decoded actions, RNG states, compute counts and projection-read
  counts were identical with N34 disabled.
- `n34-selected-tests.log`: 2 additional cases passed, proving ordinary selection
  and eight-action execution of an N34 approach proposal in FP32 and BF16.
- `n34-edge-tests.log`: 4 additional cases passed for rotated asymmetric jaw
  centers and C0/Q0 control receipt rejection of N34 markers.
- `git diff --cached --check` passed before commit; final tracked tree is clean.

Thus all 84 current N34 cases were exercised across the last three focused runs.
Warnings were existing invalid-escape and dependency deprecation warnings.
There were no failed CPU tests. Commands and results are in
`implementation-result-v1.json`; `evidence-hashes-v1.json` binds the evidence.

`cpu-evidence-v1.json` contains ten independent audit summaries. In the original
outside/entry fixtures, each dtype had ten changed proposals and zero selected
proposal-content decisions. Those nonselection results are retained. In the
separate target=.06 synthetic selection fixture, ordinary scoring selected the
proposal in each dtype and the audit verified all eight executed actions; after
its archive retention, later identical proposals correctly became no-ops.
Nonfinite and empty-gap fixtures produced zero changed proposals. None of these
counts is a physical grasp or Dev success result.

## Implementation choices and limits

The audit intentionally retains N31's independent lineage checks instead of
weakening the generic or N32 audit. Native GPU cell assignments remain recorded
inputs, not independently recomputed here. Model output is not replayed. Packet
nonfinite bytes can be preserved for a no-op, while plan/score/projection checks
remain finite. Source hashing is excluded from the inherited overhead counter;
CPU timings are not GPU latency evidence. Synthetic binding IDs use the
registered base commit as a fixture label; actual implementation identity is the
commit and source-byte manifest above, not a production release attestation.

Physical success, real controller response, GPU costs/latency, fresh matched Dev
gains and scientific promotion remain **Unknown/not evaluated**. Score: `null`.
All prior failures, costs and Unknowns are preserved. The authority's retained
62.81145837588456 GPU-hours and 442 dispatched attempts were not altered; this
executor added zero GPU dispatches and made no ledger/state writes.

## Blockers and exact next steps

No remaining CPU implementation blocker was found. Production release plumbing
is intentionally separate and is not authorized by this result:

1. Root reviews/cherry-picks the commit and creates a distinct N34 launch/worker
   integration using unchanged Q0 static/pretest overrides and explicit N34
   task/source/fresh-run binding.
2. Apply the existing N32/N32R3 source closure and loaded-module attestation
   patterns, with N34 files included and an independently frozen expected config
   hash/source manifest. Preserve the pinned RDT submodule rules. This checkout's
   RDT submodule is uninitialized; no fetch, replacement or release attestation
   was attempted. Verify the actual deployed controller's delta semantics.
3. Require unchanged generic audit acceptance plus `n34_observed_jaw_audit` for
   N34 receipts; keep fresh matched C0/Q0 controls and N34 identity distinct.
4. Prepare/review fresh matched Dev identities, original scientific gates and
   budget/reserve arithmetic before any separately authorized native release.

Detailed source mapping and integration instructions are committed in
`docs/experiments/n34_cpu_implementation.md`. No prospective protocol candidate,
root approval, release or dispatch authorization was created. No research-state,
checkpoint, tree, ledger, owning-worktree or lock/lease edits were made. STOP was
absent and the authority deadline remained open at the start and final check.
