# Protocol — run_020 H2 reward-degenerate QD calibration

Status: `LOCKED BEFORE IMPLEMENTATION`

Hypothesis: H2-v2 in `docs/01_specs/2026-08-12-eds-qd-autoresearch-v2-quality-selection-design.md`.

This iteration authorizes a read-only, zero-model, zero-GPU, zero-API, zero-LIBERO analysis plus tests for the analysis code. It does not authorize core algorithm/config changes or online dispatch.

## Inputs

- owned run_010 raw metrics, stage events, qualitative mechanism traces and archive timelines;
- historical EDS-QD raw metrics/reports under the declared read-only roots;
- `core/qd_ed.py`, relevant QD integration in `core/rdt_policy_steer.py`;
- owned runtime cache `run_010_causal_envelope_candidate/runtime_cache/cached_functions/stage{1,2}_guidance.txt`;
- primary QD literature: Mouret & Clune, *Illuminating search spaces by mapping elites*, arXiv:1504.04909; Chatzilygeroudis et al., *Quality-Diversity Optimization: a novel branch of stochastic optimization*, arXiv:2012.04322.

Every source must be read-only and recorded with path and SHA-256 where local. No result or metadata may be written beside historical inputs.

## Frozen analysis

For every valid QD metric row, classify exact-degenerate quality only when all finite candidate/archive reward values available for that chunk are exactly equal. Report separately:

- exact-zero and equal-nonzero chunks;
- task, split/profile, episode outcome, global step, guidance state if observable;
- QD selected fingerprint/source and archive occupancy;
- evaluation count, score-call count, fallback/nonfinite/accounting fields.

For every saved mechanism trace with a matching archive timeline:

1. reconstruct action fingerprints from canonical float32 action bytes;
2. bind final archive entries to saved action/reward tensors;
3. verify current reward/fingerprint selection exactly;
4. replay at least two permutations of equal-quality candidates to test whether the task-agnostic fingerprint tie changes the chosen action;
5. replay the proposed control-fallback decision without selecting a counterfactual task outcome;
6. verify every nondegenerate stream preserves current archive entries and global-best fingerprint.

No future success, environment state after the chunk, evaluator label, old formal result, or validation result may be used as an online feature. Episode success can only stratify the retrospective prevalence report.

## PASS gates

- at least 20 exact-degenerate valid QD chunks across at least 5 tasks;
- Stage-2 constant-zero guidance source and checksum verified;
- current equal-quality winner proven task-agnostic and fingerprint-dependent;
- proposed fallback maps to an existing non-QD EDS branch with projected 176 evaluations and 11 score calls;
- all eligible nondegenerate replays preserve current archive/global-best identity;
- deterministic rerun hashes match;
- strict credential scan and write-boundary audit pass.

PASS authorizes exactly one new protocol for TDD implementation of `reward_degenerate_control_fallback_v1`. FAIL concludes H2-v2 offline with no online episode.

## Required outputs

- implementation/test code only for this diagnostic;
- `experiments/run_020_quality_selection_calibration/analysis.md`;
- deterministic machine-readable analysis under the owned artifact root;
- append-only state/log/findings/trajectory/canonical-ledger records;
- implementation commit followed by result/reflection commit.
