# Protocol — Run041 protected-quality secondary-lane replay

Status: `LOCKED BEFORE ANALYZER IMPLEMENTATION OR AGGREGATE RESULT`

Parent design commit: `97c04184c2f7335b0fa2acfe7cb50026cd5c0727`. Hypothesis: `H5-v5`.

This protocol authorizes one read-only, zero-GPU/API/model/LIBERO replay and analyzer tests. It does not authorize core/config implementation, reservations, online evaluation, Dev, validation or formal use.

## Frozen inputs and source bindings

- Exact 24 trace/264 stream manifest: `experiments/run_040_within_cell_aliasing_diagnostic/input-manifest.json`, SHA-256 `2cd1f8249daebbbba69b650b5a61c89c879fa6605177f151bff4edaea7fb96e2`.
- Validated Run040 replay implementation: `scripts/eds_qd_within_cell_aliasing_diagnostic.py`, SHA-256 `58771912ddb5578845b6d68f9e17ff92528a093c3c5d161cde634fa60ca644e0`.
- V5 design SHA-256 `bc1beace04309ead43c50de644696ece1c4d097484f8f12218be5f660cd9bd5a`.
- Production `core/qd_ed.py` / `core/rdt_policy_steer.py` remain bound to `4a43cc2…b653` / `bdc523f6…d41`.

Run040 exclusions remain exact: no recursive discovery, controls, stale/incident output, video/success/outcome, future observation, evaluator/formal state or protected untracked design.

## Frozen protected archive reconstruction

For each trace, process `initial` and `full_process_after_rollout 0..9` using the Run040-validated stream/stage/bounds/fingerprint feature alignment.

Archive state is two role-separated maps:

1. `quality`: an unchanged capacity-one `ReplayArchive`. Its update, rebin, visits, reward map and global best are the comparator and must exactly replay saved telemetry.
2. `secondary`: at most one entry for each currently occupied quality cell; it has no visit counter and never changes quality decisions.

At initial/update, first snapshot the prior quality+secondary entries and append the current 16 candidates. Update quality using capacity-one rules only. For every resulting occupied quality cell, choose the best fingerprint-distinct nonquality entry from the snapshotted pool that maps to that cell, ordered `(reward desc, fingerprint asc)`; cells without an alternate have no secondary.

At causal rebin, independently rebin quality exactly as capacity one, including visits. Map all pre-rebin quality+secondary entries under the new bounds; for each resulting quality cell choose the best mapped nonquality alternate. Any entry mapped to a cell with no quality is discarded. Therefore secondary cannot create a cell, move visits, displace quality or alter global-best selection.

Before iterations 0..9, allocate exactly one global-quality anchor plus production sparse15 using only the quality map and visits. Cell counts must exactly equal the capacity-one 1+15 comparator. Within each cell, stateless SHA-256 start + round-robin selects quality/secondary; secondary is never the dedicated anchor or final execution candidate. Total parents remain16.

## Confirmatory gates

PASS requires:

1. all source/input bindings and exactly 24 traces/264 streams/4,224 candidates match;
2. capacity-one saved telemetry replay mismatch is zero;
3. protected quality fingerprint/reward/occupied-cell/visit/global-best mismatch versus capacity-one is zero after every stream/rebin;
4. all 240 allocation cell-count maps equal the capacity-one production 1+15 maps, each totals16, and final-selection fingerprint equals capacity-one global best;
5. secondary never occupies a nonquality cell, duplicates quality, exceeds one/cell, carries visits or becomes anchor/final selection;
6. at least `20%` of 3,600 sparse slots select secondary; allocated-cell coverage retention is exactly1.0;
7. Run040 collision count/ratio and top-two direction/shape/reward-gap medians reproduce exactly within float serialization;
8. two independent payloads are byte-identical, global Python/Torch RNG unchanged, and finite/accounting/write/credential gates pass.

PASS authorizes only a new protocol for TDD core implementation. FAIL rejects the final evidence-backed candidate; absent new task-linked evidence, the global no-progress rule requires no-adoption rather than a sixth candidate.

## Allowed writes

- Before artifacts, exactly new `scripts/eds_qd_protected_quality_lane_diagnostic.py` and `tests/test_eds_qd_protected_quality_lane_diagnostic.py`.
- After their implementation commit, dual JSON only below `/mnt/data/shared2/zhuoli/vla-pilot-plus-plus/eds-qd-autoresearch-libero-swap-ood/run_041_protected_quality_lane_diagnostic/analysis/`, mode0444.
- Result phase may add `analysis.md` and append common state/findings/log/ledger/trajectory.
- Core/config/GPU/API/model/LIBERO/reservation/online/Dev/validation/formal authorization remains zero.
