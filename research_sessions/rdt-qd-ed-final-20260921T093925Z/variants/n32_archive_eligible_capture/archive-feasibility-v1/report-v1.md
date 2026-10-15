# Node 15.2 bounded CPU archive feasibility

Status: descriptive_measurement_complete. Scope SHA256 `67c3bc258e6f9d97a9133fe8c3f11c59d6c1b89bb12bf1ede2ca5addce82ccce`.

Verified 1428 exact listed bundles (1254372052 bytes). Reconstructed 84 decisions. Denominator: 840 valid of 840 listed opportunities; 0 Unknown and 0 contradictory opportunities excluded.

Global best eligible: 32/840. Secondary-parent additional eligibility: **95/808 valid best-abstaining opportunities** (95/840 valid total).

| Task | Listed | Valid | Best eligible | Additional | Unknown | Contradictory |
|---|---:|---:|---:|---:|---:|---:|
| 0 | 150 | 150 | 2 | 0 | 0 | 0 |
| 1 | 120 | 120 | 6 | 32 | 0 | 0 |
| 2 | 280 | 280 | 17 | 27 | 0 | 0 |
| 3 | 30 | 30 | 0 | 10 | 0 | 0 |
| 4 | 200 | 200 | 6 | 26 | 0 | 0 |
| 5 | 60 | 60 | 1 | 0 | 0 | 0 |

Resource use: 54.476 CPU seconds; 45.737 wall seconds; peak RSS 512569344 bytes. Limits: 600 CPU seconds / 900 wall seconds / two threads / 4 GiB; CUDA hidden.

Root decision rule unchanged: If zero additional eligibility on all auditable listed opportunities, stop N32 before GPU release. Positive eligibility only licenses a later integration/auditor review; Unknown requires bounded diagnosis.

Positive eligibility supports only later integration/auditor review. Unknown/contradictions still require bounded diagnosis. No GPU release.

Exact command:
```sh
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python ../archive-feasibility-v1/analyze-v1.py
```

Analysis script: `analyze-v1.py`; detailed result and exact input/source hashes: `result-v1.json`; final output hashes: `output-hashes-v1.json`.

Limitations:

- Descriptive counterfactual on listed accepted N31 Dev opportunities only; no task success, physical capture, fresh efficacy or scientific promotion is established.
- Recorded provider recognition/target index are inherited from accepted evidence. Provider files were not accessed or executed; internal packet/tracker/provider hash consistency was checked, not independent source-template recognition.
- Original native cell assignments/projections/rewards are inherited. No GPU cell arithmetic, projection, reward, model or simulation recomputation; this is not a rerun of the accepted auditor.
- Counterfactual selection does not alter subsequent recorded N31 archives: each opportunity starts from its factual preceding N31 archive, not an N32 rollout.
- Unknown/missing and contradictory associations are excluded from valid denominators and never counted as negative eligibility. Multiple identical occurrences are content associations, not unique lineage.
- CPU selector cost excludes future device transfer, runtime recording and production integration. Additional eligibility only supports later integration/auditor review, never GPU release.
- Only frozen listed bundles were decoded; omitted decisions/tasks are not negative evidence.
