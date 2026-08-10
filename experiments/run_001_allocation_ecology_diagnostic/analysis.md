# `run_001_allocation_ecology_diagnostic` Analysis

Status: `INVALID`

Label: `INFRASTRUCTURE_FAILURE`

Decision: `INVALID_CONCLUDE_AND_TRIGGER_OUTER_LOOP`

Protocol commits: v1 `dcf234b6999165de0a5bca4a8e44332896cc61dc`; v2 `91ddd34f64d129549147f42c64244b552398a624`; v3 `f6d7bc9a1d579fcbb55e36905beafd1a2ba8264c`; v4 `3d320f6a143a74cbc31625f2f12ccdd77995c7f4`.

## Outcome first

This run produced no admissible H4 result. It must not be cited as evidence that quality inheritance is positive or negative, and it does not authorize a quality-reserve algorithm candidate. The best stays `2/10`, the target gap stays 3, and no online episode, GPU, model, reward, VLM, environment or action call occurred.

Two aggregate attempts failed the preregistered trace-validity gate for different analyzer/telemetry semantic assumptions. V4 explicitly prohibited another repair after a further validity failure, so the run ends `INVALID` and triggers outer-loop infrastructure reflection. The next target-linked direction is H1 partition diagnostics, not another H4 analyzer repair.

## Attempt provenance

| Attempt | Protocol state | UTC / wall | What passed | Validity failure | Artifact SHA-256 |
| --- | --- | --- | --- | --- | --- |
| initial | v2 | `15:28:02–15:28:47Z` / 45.20 s | 27 profiles, 540 files, 9,000 stages, immutable roots | analyzer constrained population occurrence ranks to 1..16 and rejected all 360 budget traces | `c59cbe979706320fb90ecee7a1bfe874fe3222b5f0578a23fa3b0b2e0c5e24b5` |
| recovery | v4 | `15:34:09–15:34:41Z` / 31.61 s | 27 profiles, 540 files, 9,000 stages, 374,400 children, immutable roots | 52 sparse traces contained zero-slot archive cells; v4 incorrectly treated nonpositive slot counts as malformed | `489a7156b8d91faab5aa1f365597628f268479d45d5604f3af2c1bcf886efda0` |

The first failure motivated source-faithful reconstruction: `parent_ranks` rank population occurrences, while a 16-cell quality rank must group repeated occurrences using the numerically sorted slot map. The second failure revealed that sparse-priority allocation can legitimately assign zero children to some occupied cells when visit weights are skewed. A full archive is therefore not equivalent to positive slot coverage of all 16 cells.

These are instrumentation lessons, not H4 support. All reward-margin, bootstrap, family and task-subgroup values in both invalid JSON files are inadmissible because the trace inclusion rule failed.

## Validity result

| Gate | Initial | Recovery | Final |
| --- | --- | --- | --- |
| exact 27 profiles | PASS | PASS | PASS |
| exact 540 traces / 9,000 stages | counts PASS; semantics FAIL | counts PASS; semantics FAIL | FAIL |
| immutable source roots | PASS | PASS | PASS |
| deterministic canonical replay | not reached | not reached | NOT RUN |

Recovery failure counts: 52 trace files contained at least one zero-slot cell; the most frequent affected iterations were late sparse iterations. The analyzer loaded all files with `weights_only=True`; no unsafe-load, missing-stage, nonfinite-reward, root-boundary, population-length or stage-count error occurred.

## Target-linked decision

- Success/task change: none; zero episodes.
- Best / target gap: `2/10`, gap 3 before and after.
- H4 status: unresolved due invalid telemetry analysis; online H4 allocation candidate rejected for this cycle.
- Why stop repair: v4 preregistered that any additional validity failure triggers infrastructure review; continuing would become analyzer exploration disconnected from the `>=5/10` objective.
- Next: outer-loop reflection, then a clean H1 partition diagnostic using JSONL shadow candidate streams and existing overflow/task evidence.

## Artifacts

- Invalid initial JSON: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_001_allocation_ecology_diagnostic/analysis.json`, SHA-256 `c59cbe979706320fb90ecee7a1bfe874fe3222b5f0578a23fa3b0b2e0c5e24b5`.
- Invalid recovery JSON: `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_001_allocation_ecology_diagnostic/repaired_v3/analysis.json`, SHA-256 `489a7156b8d91faab5aa1f365597628f268479d45d5604f3af2c1bcf886efda0`.
- Final analyzer source (preserved for audit): SHA-256 `520a1ac5ec0088d9f5f4ec97d4c1263e131be3497a57328c52cec5b746b9e579`.
- New online episodes / attempts / GPU-hours: `0 / 0 / 0`.
