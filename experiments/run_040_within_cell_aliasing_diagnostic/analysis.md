# Run040 result — aliasing supported, naive top-2 candidate rejected

Decision: `REJECT_H5_V4_TOP2_RETENTION_FAIL_TRIGGER_OUTER_LOOP`.

Run040 is a valid zero-episode diagnostic. The repaired v2 analyzer exactly replayed the saved capacity-one archive with zero mismatches across 24 traces and 264 streams. Canonical/replay artifacts are byte-identical, mode 0444, file SHA-256 `447152dbc7e0448e7b29082b76117f90f52094d7f0d6f5dfd855a2daa0ea9b98`, and strict credential hits are zero.

## Result

- 4,224 candidates; 2,750 candidates in colliding endpoint-XY cells (`65.1042%`); 1,019 colliding cells.
- Same-cell reward top-two normalized direction/shape distance medians: `0.361670 / 0.250086`.
- Same-cell reward top-two reward-gap median: `0.0126953`.
- Capacity-two secondary sparse slots: `1,001/3,600 = 27.8056%`; XY-cell coverage retention median: `1.0`.
- Capacity-one exact replay mismatches: `0`; capacity-two capacity/fingerprint mismatches: `0`.
- Capacity-two quality-retention mismatches: `17`, across six traces and tasks 0/3/6/7/9.
- Gates: `14/15 PASS`; sole failure is `capacity_two_quality_and_global_best_retention`.

## Interpretation

The aliasing mechanism is strongly observed: endpoint-XY capacity one removes many reward-near but trajectory-distinct candidates, and a second lane would receive meaningful parent budget at fixed 16 slots. However, the frozen naive rule “merge all history and retain overall reward top two” does not preserve the comparator quality lineage under causal-envelope rebins. Secondary history can enter a newly merged cell and displace the lineage the candidate was required to protect. That violates the preregistered retention gate before any online use.

This is not evidence against all within-cell plurality. It rejects `qd_within_cell_top2_v1` specifically and identifies a narrower successor: keep a protected quality lane whose update/rebin exactly follows capacity-one semantics, plus a separate secondary lane that cannot evict the protected lineage. Any successor requires a new versioned protocol and a fresh replay; no threshold relaxation or reuse of this candidate is allowed.

No core/config change, GPU, API, model call, LIBERO episode, reservation, Dev, validation or formal evaluation occurred. Historical formal best remains `2/10`, target gap `3`.
