# Result — run_022 reward-degenerate fallback offline mechanism preflight

Status: `PASS — ONLINE MECHANISM PROTOCOL MAY BE DESIGNED`

Protocol commit: `cb87d75f7779569889994ae3e2efff64e0942ec7`

Harness implementation commit: `786e7ed1310fb77bc33b2c04b965c50a45173eeb`

## Implementation TDD record

The first dedicated test stopped before a scientific case because an independently imported script did not add the repository root to `sys.path`. The second red execution reached active QD and failed its built-in final-selection hard gate because the draft synthetic rollout used decimal float64 carrier increments that did not round-trip exactly through the archive's float32 reward tensor. No artifact, GPU work, API call, model load, LIBERO reset, or attempt reservation occurred in either red execution.

Both were harness implementation defects within the locked two-new-file boundary. The final harness explicitly imports from the repository root and uses deterministic binary-exact rollout carriers. The protocol's float64 population, initial exact-zero/equal-negative/`1e-12`/nondegenerate rewards, seed, algorithm blobs, thresholds, cases, comparisons, accounting, and gates did not change.

## Test evidence

- Integrated eight-case suite plus same-instance sequential probe: PASS.
- Dedicated harness tests: `3 passed in 97.33s`.
- Run-021 focused fallback regression: `6 passed, 361 deselected`.
- QD archive regression: `22 passed`.
- Harness/test py_compile: PASS.
- Existing core/config changes after run_021: none.

Harness SHA-256:

- script: `6bd193516e39f4175662ab312d1b75523957fe7b5532e85492a3e0c5dc43a4ad`
- test: `a777e4c76ea8ee266949fb9dc7dd4b33bd0a671edf7935bc00b49ca2536a3e3b`

## Integrated case results

| Case | Trigger | Active QD | Selected source | Selected fingerprint | Final-action-set SHA-256 |
| --- | ---: | ---: | --- | --- | --- |
| candidate exact zero | yes | no | fresh | `01d89d4e…74a3c` | `5891b67a…cb82b` |
| EDS control exact zero | no | no | fresh | `01d89d4e…74a3c` | `5891b67a…cb82b` |
| legacy QD exact zero | no | yes | qd_archive | `001564f8…d261` | `03dc76fd…13b4a` |
| candidate equal -0.25 | yes | no | fresh | `01d89d4e…74a3c` | `5891b67a…cb82b` |
| candidate near equal (1e-12) | no | yes | qd_archive | `e13b75b0…9d4f` | `4b0b28a7…0661` |
| legacy QD near equal | no | yes | qd_archive | `e13b75b0…9d4f` | `4b0b28a7…0661` |
| candidate nondegenerate | no | yes | qd_archive | `e13b75b0…9d4f` | `4b0b28a7…0661` |
| legacy QD nondegenerate | no | yes | qd_archive | `e13b75b0…9d4f` | `4b0b28a7…0661` |

Exact-zero candidate and EDS control also match in selected tensor, ordered final actions, final scores, selected source, and terminal Torch RNG checksum. Candidate/legacy near-equal and nondegenerate cases additionally match full initial/per-iteration archive snapshots, bounds checksums, cell visits, QD accounting, and terminal RNG.

The same-instance sequential probe first triggered fallback on exact zero, then activated QD on the following nondegenerate chunk with `qd_evaluation_count=176`; there is no persistent fallback state.

All eight complete cases record 176 search evaluations and 11 score calls with zero nonfinite, action-mask, archive-accounting, elite-monotonicity, or final-selection violations. Fallback QD evaluations are 0; active-QD evaluations are 176.

## Determinism and immutable artifacts

- Fixture SHA-256: `78a639bad81b6577dbb6486e7b6292ae410b1a5384f9d419fe208074badc979a`
- Scientific payload SHA-256: `8fd3f06bb1ea0a4224b30329f5d3e853f7700cb6cb339193a4474b653f26c13e`
- Independent replay SHA-256: identical.
- Canonical/replay file SHA-256: `320fabf54847c77d944ed0ff5bdc2c530331c765d3bcfbef2aa5173c46279bac`
- Both files: 513,735 bytes, mode 0444, byte-identical.
- Strict credential matches: 0.
- Artifact root: owned `run_022_reward_degenerate_mechanism_preflight/analysis` only.

## Target and budget impact

This is causal integration evidence, not task success evidence. Added online episodes, reservations, GPU hours, validation uses, and formal uses are all zero. Historical formal best remains 2/10 and gap to the required 5/10 remains 3.

## Decision

`KEEP_OFFLINE_MECHANISM_PASS_AND_AUTHORIZE_ONLINE_MECHANISM_PROTOCOL_ONLY`.

Before any online reservation, a new protocol must freeze exactly six short mechanism cells, paired profile bindings, a runner/audit interpretation for configured-but-inactive QD chunks, algorithm/checkpoint/input/cache hashes, immutable manifest, GPU admission, safety/latency/artifact/credential/write-boundary gates, and attempt/GPU budgets. Dev-A, Dev-B, validation, and formal remain unauthorized.
