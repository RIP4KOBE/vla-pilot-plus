# N34 CPU implementation and root integration

N34 is an independently opt-in `observed_jaw_approach_v1` profile. It changes one
post-rollout offspring slot (15) per ordinary QD iteration, using the current
archive global best's canonical native plan as the template. It does not change
quality, archive retention, parent allocation, ED selection, the other 15
candidates, or template entries after slot 7.

The literal N31 prism is inclusive: x in [-.008,.008], y in
[qpos[1]+.0005,qpos[0]-.0005], z in [-.0116,.0044]. Empty means lower > upper,
exactly as N31. Geometry uses binary64 and N31's normalized xyzw rotation.
Outside the currently observed prism, the command is
`clip((target - EEF - R @ (0,(lower+upper)/2,-.0036))/(8*.01),-1,1)` for
all eight translation slots, zero rotation increments, and gripper -1.
Observed entry closes immediately with gripper +1 and zero translation/rotation
for all eight slots. Projected future entry never closes. Each decision starts
with a new context/cache; no closure state survives a decision or stage reset.
Missing or nonfinite required proprioception produces no competitor. Malformed
packet identities/shapes and contradictory provenance fail closed.

## Native representation proof

`_RDTModelAdapter.encode_inputs` in `core/rdt_policy_steer.py` constructs a 128D
action mask with ordered action indices [39,40,41,42,43,44,10]. These differ from
the state indices [0,1,2,3,4,5,6,10,11]. The production
`rdt_action_to_libero_raw` decoder directly extracts those action slots into
float32 and binarizes only the gripper; it applies no affine normalization or
absolute-orientation/ortho6d conversion. `encode_libero_prefix` is the matching
inverse for binary gripper commands, preserving every unrelated template byte.
Thus channels 42:45 decode to exactly zero normalized rotational increments;
old absolute-pose slots 30:39 are never zeroed.

The LIBERO adapter's postprocessor has no action steps. Its `step` forwards the
six decoded channels unchanged (float32), binarizing only the gripper. The inner
wrapper forwards that command directly. The configured environment uses
OSC_POSE. The .01 constant is the existing trajectory projector convention,
**not a demonstrated physical displacement gain**. The release must still
attest the real loaded controller's delta semantics and source/version; CPU
fixtures do not certify a deployed simulator installation.

Tests execute the actual production input encoder with lightweight image/model
services in FP32/BF16, encode/decode the proposal with sentinel unrelated slots,
and exercise the actual policy and Main observation paths. Full base-method
parity compares native canonical populations, decoded action, RNG state, and
compute counts for C0/Q0/N31/N32 against commit
`04d1255016fa13a2d467995b9e37a6a829356a1c` in both dtypes.

## Evidence and independent audit

N34 records `n34_observation_context`, `n34_canonical_cache`,
`n34_capture_dwell_opportunity`, and `n34_archive_update`. The scalar schema is
`n34-observed-jaw-scalar-v1`; no receipt identifies this method as N32.
Inherited N31 cache/association/insertion code is reused without invoking its
predicted-entry proposal. Algorithm-specific runtime receipts bind the actual
resolved config hash, explicit task/source/run binding, and source hashes.
They are **not a substitute for full runtime source closure**.

`scripts/qd_ed_n34_reference.py` independently reconstructs geometry and explicit
native channel writes without importing the production proposal/encoder.
`scripts/qd_ed_n34_native.py` retains N31's independent canonical-source,
parent, retention/tie, ordinary-selection, decode, commit, and execution checks,
and adds an externally supplied N34 config/source identity. It binds the raw
observed packet, tracker/provider, current best template, before-substitution
other-15 commitment, scored candidate, and final executed prefix. It records
content-source ambiguity rather than inventing unique provenance. It inherits
native recorded cell assignments; it does not independently replay GPU cell
arithmetic or the model. Nonfinite packet bytes are compared exactly without
relaxing finite requirements for plans, scores or projections.

Use the unchanged generic audit first, then:

```python
from scripts.qd_ed_n34_native import audit_output
report = audit_output(output_directory, generic_report,
                      expected_runtime=reviewed_manifest["expected_runtime"])
```

The audit gate is `n34_observed_jaw_audit`, schema
`n34-independent-observed-jaw-v1`. `expected_runtime` must be generated from a
prospectively reviewed source/config manifest, never inferred from candidate
receipts. The tests derive a local fixture anchor explicitly for synthetic
CPU checking only. The original Q0 mechanism-pretest overrides are retained in
native audit tests; frozen production cost expectations include those probes.
Existing N31/N32 audits and release gates are unchanged.

## Exact remaining root integration

1. Review/cherry-pick this isolated commit. Add a distinct N34 profile to a new
   release/worker bridge; existing N32/N32R3 controllers intentionally reject
   N34. Compose `candidate_n34.json` with the unchanged Q0 static/pretest launch
   overrides and an explicit `n34_runtime_binding` with task ID, approved source
   commit and fresh attempt/run ID. Both N31 and N32 modes must remain off.
2. Follow `qd_ed_n32_bridge.py` and `qd_ed_n32r3_bridge.py` for prospective
   composition, source manifests and loaded-module attestation. Include N34
   production, reference, audit, config and tests; bind actual operational and
   scientific source identities explicitly. Retain the existing pinned RDT
   submodule/source-closure rules, including `scripts.maniskill_model`. The RDT
   submodule is uninitialized in this CPU checkout; it was not fetched or
   substituted. Do not relabel N34 as N32 to reuse a launch path.
3. Freeze an independent expected runtime object with `binding`, the hash of
   the fully resolved EDS config, and the relative-path hashes listed in
   `core.qd_observed_jaw_approach.SOURCE_FILES`. Freeze the wider loaded runtime
   separately, including decoder, adapter/controller and model dependencies.
   Require unchanged generic audit acceptance and the N34-specific gate before
   accepting an N34 terminal record; controls must have no N34 evidence/metrics.
4. Prepare fresh matched Dev identities/controls and budget/reserve arithmetic
   under the existing original scientific gates. Resolve source closure and
   actual controller delta semantics before release. Obtain root's release
   decision through the existing coordinator procedure. This commit creates no
   approval, release, dispatch flag, reservation or protocol amendment.
5. Only separately authorized native Dev work can establish actual approach,
   observed entry, selection/execution, physical capture and matched success.
   Preserve prior failures, costs, and all Unknowns; this CPU work changes none.

Physical success, GPU latency, actual controller response and fresh matched Dev
improvement remain **Unknown**. CPU/geometry correctness is not scientific
promotion. No full historical native replay or protected data was used.
