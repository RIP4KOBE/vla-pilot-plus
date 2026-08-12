# Protocol v2 — Run040 result-classification repair

Status: `LOCKED AFTER V1 ARTIFACTS, BEFORE ANALYZER REPAIR OR V2 ARTIFACTS`

Parent protocol commit: `2a6444a`. Analyzer implementation commit: `4d22541`.

The first dual replay completed deterministically and produced byte-identical mode-0444 artifacts, both file SHA-256 `71cef1fd1f6a768d363e9349db535cdf9a0fde5c8008eae1e2114a487c555540`. It revealed a result-schema defect: one list named `exact_mismatches` mixes capacity-one historical-replay mismatches with capacity-two counterfactual retention mismatches. All 17 listed items are `quality_retention` checks from the capacity-two candidate, but the aggregate metric and gate incorrectly label them `capacity_one_exact_mismatch_count` / `capacity_one_exact_replay`.

This protocol authorizes only:

1. split trace mismatch recording into `capacity_one_mismatches` and `capacity_two_mismatches`;
2. report separate aggregate counts and gates: capacity-one exact replay, capacity-two quality/global-best retention, and capacity-two capacity/fingerprint integrity;
3. add/adjust tests proving capacity-one and capacity-two failures cannot be conflated;
4. generate new `canonical-v2.json` and `replay-v2.json` after the repair commit.

The 24 inputs, checksums, stream alignment, feature math, archive/rebin/update/allocation counterfactual, thresholds, success exclusion and all scientific observations remain frozen. V1 artifacts remain immutable and must not be deleted or overwritten. A v2 FAIL is the Run040 scientific result; no threshold or mechanism change is allowed.

Allowed worktree changes before v2 artifacts are exactly the existing Run040 analyzer and test. Core/config/GPU/API/model/LIBERO/reservation/Dev/validation/formal authorization remains zero.
