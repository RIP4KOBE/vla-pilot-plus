# Protocol — Run045 global no-adoption conclusion

Status: `LOCKED_BEFORE_DECISION_MANIFEST_OR_FINAL_REPORT`
Date: 2026-08-12
Parent result commit: `374b428`

## Decision question

Determine whether the frozen continuous-loop rules authorize another EDS+QD
candidate after Run044, or require convergence to
`CONCLUDE_NO_ADOPTION_WITHIN_GLOBAL_BUDGET_TARGET_NOT_MET`.

The primary target remains formal LIBERO-PRO `libero_object_swap >=5/10`.
Historical formal best is `2/10`, so the unresolved target gap is three. No
mechanism proxy can change that value.

## Frozen evidence set

The conclusion must bind and synthesize, without rerunning or rewriting:

- the approved base design and v4/v5 versioned designs;
- v3 final report/decision and Run033–034 task evidence;
- Run040 v4 capacity-two retention FAIL;
- Run041–043 protected-lane offline/implementation/CPU PASS evidence;
- Run044 original identity incident, repair/recovery protocols, immutable
  manifests/ledger/incident archive, valid recovery audit and result commit;
- current Git branch/HEAD, core/config fingerprints, protected-file exclusion,
  artifact/write boundary, credential audit and budget accounting.

## Frozen reasoning rule

The v4 design stops autonomous search after two consecutive versioned cycles
without task-level gain when no new task-linked evidence supports a non-repeated
EDS+QD core hypothesis. V4 produced no online candidate because its sole
capacity-two mechanism failed quality retention. V5 repaired that exact failure,
passed offline and CPU gates, then produced `0/2 -> 0/2` online with no gained
task and failed universal secondary activation in 3/410 iterations.

Run044's 1,685 aggregate secondary parents are new mechanism observations but
not new task-linked progress: 407/410 positive iterations still yielded zero
successes, so guaranteeing the remaining three iterations would be an adjacent
activation repair without evidence that it can shrink the target gap. The base
design forbids continuing merely to improve a mechanism metric. Stage/RBF,
reward/model, broad sweeps and non-EDS+QD changes remain out of scope; all five
evidence-backed QD directions have now been tested or eliminated.

Therefore the deterministic outcome is global no-adoption. A sixth candidate,
Dev-A, validation, formal evaluation, gate relaxation or outcome-driven rerun
must not be authorized. This is target-directed convergence under the no-progress
rule, not a claim that the target was achieved.

## Documentation-only authorization

After this protocol commit, only the following may be created or updated:

- one immutable mode-`0444` decision manifest under the owned Run045 artifact
  root;
- one final human-readable report under `docs/03_evidence/eds_qd_autoresearch/`;
- `research-state.yaml`, `research-log.md`, `findings.md`, and the unified
  iteration ledger.

No code/config/test, GPU/API/model/LIBERO process, reservation, recovery,
validation or formal episode is authorized. The decision manifest must include
source/result hashes, task matrix, negative/invalid evidence, gates, GPU and
reservation accounting, credential/write boundary, protected untracked-file
exclusion and final decision. Credential value or fingerprint is forbidden.

Final accounting must remain 70 effective online episode attempts, 98/144
reservations, `6.9468320556/48` GPU-hours and zero formal episodes. The final
report must plainly state that `>=5/10` was not reached, identify the strongest
mechanistic findings and explain why additional exploration is not authorized.
