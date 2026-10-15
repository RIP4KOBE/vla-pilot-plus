# Task0 actual final-population membership

Both authorized, unchanged CPU checks completed successfully. All 29 C0 and 52 Q0 eligible decisions had a **distinct-latent, nonflagged actual final member**, but **none** had a distinct-latent nonflagged final member with original effective quality >= the actual selected quality. The best nonflagged final member has a strictly negative quality gap in all 5 C0 A-witness decisions and all 17 Q0 A-witness decisions. This establishes an observed original-objective tradeoff, not a counterfactual outcome or proposed replacement rule.

“Nonflagged” means only not exceeding the already frozen projected `d8−d7` native-ULP regression screen. It does not establish physical non-regression. The table includes every guided eligible decision; A/non-A stratification was descriptive and did not determine inclusion.

| Episode / original A stratum | Decisions | Distinct nonflagged final member exists | Distinct nonflagged final quality ≥ selected | Best nonflagged delta negative | Best nonflagged delta zero |
|---|---:|---:|---:|---:|---:|
| C0, all | 29 | 29 | 0 | 10 | 19 |
| C0, A | 5 | 5 | 0 | 5 | 0 |
| C0, non-A | 24 | 24 | 0 | 5 | 19 |
| Q0, all | 52 | 52 | 0 | 31 | 21 |
| Q0, A | 17 | 17 | 0 | 17 | 0 |
| Q0, non-A | 35 | 35 | 0 | 14 | 21 |

Zero best-nonflagged gaps refer to the already selected latent. They do not indicate a different latent with equal original quality. No best-nonflagged gap was positive. C0's overall signed range is `[-0.042327880859375, 0]`; its A range is `[-0.042327880859375, -0.0007781982421875]`. Q0's overall range is `[-0.03466796875, 0]`; its A range is `[-0.002864837646484375, -0.0000019073486328125]`. Every original quality association, signed gap and exact tied maximum remains in the JSON outputs.

C0's 464 native final slots were verified against its identical last canonical batch, whose recorded per-row quality supplies the final quality. Q0's 818 native final slots were verified against its recorded archive-elite population; all native-matching historical occurrences agreed on quality in these data. Tail-unknown and quality-unknown slot counts were zero in both episodes, and there were no A-Unknown eligible decisions. All 81 selected index/native-tensor/fingerprint/quality/decode checks passed. Repeated final slots and all matching historical occurrence IDs were retained. Specific archive insertion occurrence provenance remains Unknown; it was not reconstructed.

The frozen production code records the actual final pools: `core/rdt_policy_steer.py` replaces Q0's population with `qd_archive.elite_tensors()` before `final_selection`, whereas C0 retains its actual final population. The collector copies the existing native tensors. Every final slot was joined to canonical records only with matching shape, dtype, exact native bytes and canonical fingerprint. Fresh complete audits and all frozen source/input hashes passed. No archive replay, rescore, alternative action execution, changed target/threshold, model, projector, simulator or GPU call occurred. No identity/schema gate was relaxed.

The earlier historical-pool report remains unchanged. In particular, its 4/5 C0 A-witness decisions with apparently quality-preserving distinct historical candidates do **not** establish such an option in the actual final population: the direct final check found 0/5. Historical scoring-time availability and final decision-time membership are different evidence claims.

Both original episode outcomes remain `success=false`. Their 61 C0 and 38 Q0 excluded decisions remain excluded. Actual final membership does not say what would happen if an unexecuted member were chosen, and the two episodes cannot establish a success-rate change. Decisions and slots are correlated within an episode. No task5, observer=false, external GPU2, validation/formal evidence or terminal-invalid episode was included. `promotion_status=NOT_EVALUATED`; counterfactual success remains Unknown.

Runtime and identity evidence:

- Root authorization `authorization-v1.json`: SHA `c209ccf2df5c1ffcdafec97be570f1eb5d006a8ac20b6af67f4236951ec567eb`.
- Script SHA `732763eef2b11909318500b4f95f8d403cf57db4da706dffb7afe53c74a0b160`; protocol SHA `9d57b9a061d9cd98c18bbc241e4e36c9f5841e9f550a43348b758c8531b18d9a`.
- `input-t00-c0-v1.json`: SHA `b399abf760953faf1540db0d74060de9fa255eb310b0fc5d705a6724d385f2b9`.
- `input-t00-q0-v1.json`: SHA `668436dd8b792498416fa91dc09b4b54180cd491cde074dfc3759d8ab20cb60a`.
- `t00-c0-v1/final-population-membership.json`: SHA `fda61dee79c6df38e1772120b44fb24adf3ec0ff00bda791bc13e4a30cc107b8`.
- `t00-q0-v1/final-population-membership.json`: SHA `40b319e2e41339cda84ba1f27cb61ff4dc71665dc4ee14ab6e46c64c0a6716b8`.
- Exact invocations, stdout/stderr and process exit records are stored alongside these files. `summary-v1.json` preserves all decision summaries and strata and is reproducible from the two digest-bound outputs with the adjacent `summarize-written-reports-v1.py`; it never opens bundles.

CPU analysis sections took 22.680002859 s (C0) and 41.104649983 s (Q0); child wall times were 24.380253934 s and 43.079650221 s. Cumulative parent peak RSS after analysis was 979,668 KiB and 1,448,140 KiB. These peaks include imports and audit work and are not exclusive analysis-memory measurements. CUDA remained uninitialized. Original W sources, queues, ledgers, inputs and historical reports were not modified.
