# Analysis — run_030 global-quality anchor allocation reconstruction

Decision: `KEEP_H4_V3_DIAGNOSTIC_PASS_AND_AUTHORIZE_IMPLEMENTATION_PROTOCOL_ONLY`

Run030 passed all nine frozen gates with zero GPU, API, model, LIBERO, reservation, or online-episode use. It is allocation-mechanism evidence, not a task-success estimate.

## Confirmatory result

- Five frozen owned files: 419/419 rows checksum-valid.
- Eligible unique-maximum transitions: 3,205 across all 10 tasks; 566 equal-maximum transitions were preregisteredly excluded because saved metrics do not contain the fingerprint tie needed to identify one global-best cell.
- Production allocator baseline reconstruction: 3,205/3,205 exact slot-map matches.
- Baseline prior-global-best cell received zero next-iteration slots in 2,151/3,205 transitions (`0.6711388455538222`).
- All ten tasks independently exceeded the task omission gate; per-task ratios ranged from `0.5356` to `0.8556`.
- Candidate reconstruction: exactly one dedicated global-best anchor plus 15 sparse slots and 16 total slots for 3,205/3,205 transitions.
- Candidate global-best zero-slot count: 0.
- Candidate/baseline occupied-cell coverage retention median: `1.0`, above the frozen `0.85` gate.
- Torch global RNG unchanged; accounting, finite, credential, input-checksum and write-boundary gates passed.

The canonical and replay files are byte-identical, mode 0444, 6,101,386 bytes, with file SHA-256 `cede7bbb823621e5ac21a3b5eb10c7ceb6e4acdf967d63ab5fb61135f472d812`. Their scientific payload SHA-256 is `7f793a70847538837bfb9a1c6a510d8d86d6178668f01165674fc9131e47c880`.

## Interpretation and target effect

The diagnostic confirms a pervasive exploit/retain failure in the causal-envelope sparse-QD allocation: cell-local quality elitism does not ensure that the best cell gets descendants. Reserving one parent slot removes that omission without reducing median covered-cell count and without changing the 16-parent budget.

This result does not show that reward predicts environment completion or that `>=5/10` will be reached. Historical formal best remains `2/10`, target gap remains 3, and formal remains disabled. The next authorized action is only a protocol-first TDD implementation of the frozen `qd_global_quality_anchor_v1` mechanism with default-path identity and `176/176/11` accounting.

## Implementation-history note

Before any confirmatory input was aggregated, analyzer TDD exposed and fixed two loader-only issues: the standalone script needed the repository root on `sys.path`, and the importlib test needed to register its module before a dataclass declaration. Neither issue changed an input, gate, transition rule, allocator call, or output artifact. Final dedicated plus production-QD tests passed 26/26 before the confirmatory run.
