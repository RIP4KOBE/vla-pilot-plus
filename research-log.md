# Research Log

Chronological, append-only record of research decisions and actions.

| # | Date | Type | Summary |
|---:|---|---|---|
| 1 | 2026-08-08 | bootstrap | Audited baseline commit `5b0898e53d5b9e16200c17479a74746071215787`, design/report checksums, read-only decision manifest, raw audit/metrics, qualitative contact sheets, QD core/config/runner/audit code, and the Grid5 traceback. Historical decision remains `no_adoption_keep_p2_stage_on_abs_rbf_control`: control 3/10, uniform 0/10, sparse 2/10. |
| 2 | 2026-08-08 | bootstrap | Created branch `exp/eds-qd-autoresearch-libero-swap-ood` and its isolated worktree from the explicit base commit. Excluded and preserved the source worktree's unrelated untracked search-budget design. |
| 3 | 2026-08-08 | bootstrap | Ran the existing CPU-only QD archive/runner/audit suite: `56 passed in 3.22s`. Initialized autoresearch state in planning-only, paused mode. No GPU, LIBERO episode, storage mutation, or scheduled continuity loop was started. |
| 4 | 2026-08-08 | bootstrap | Completed the 27-section design at `docs/01_specs/2026-08-08-eds-qd-autoresearch-libero-swap-ood-design.md`. Applied a structured problem-first/failure-boundary/decomposition/simplicity review to retain five mechanistic hypotheses and reject direct compute scaling, learned-BD-first, broad sweeps, checkpoint/Stage changes, and repeated formal selection. Preregistered split isolation, one-shot formal acceptance, promotion gates, 128 unique online cells, 15 same-cell recovery slots, a 143-attempt cap, and a 48 GPU-hour cap. State remains paused for design review. |
| 5 | 2026-08-10 | bootstrap | Revised the design from user review: `>=5/10` is the single primary objective and successful hard-gate completion stops the search; every iteration must measure its target-gap effect and cannot continue for mechanism novelty alone. Optimization is hard-scoped to the nine-step EDS+QD core chain with QD-first escalation; all other worktrees/workspace paths and historical shared2 artifacts are read-only evidence sources; every iteration is fully indexed in `docs/03_evidence/eds_qd_autoresearch/iteration-ledger.md`; future execution may dynamically use any eligible GPU 0–7 with up to eight one-worker-per-GPU slots. Preserved planning-only pause and ran no experiment. |
| 6 | 2026-08-10 | resume | User explicitly approved formal execution of frozen design commit `1aee76489ea8989a832dec49b747239f2db90981`. Transitioned state from `paused/design_review` to `active/bootstrap_historical_replay` at `2026-08-10T15:00:35Z`. Algorithm, storage, GPU, online episode and formal counters remain zero; formal evaluation remains gated. |

## Entry types

- `bootstrap` — scoping, baseline audit, literature survey, initial hypotheses.
- `inner-loop` — protocol, run, result, and keep/revert decision.
- `outer-loop` — synthesis and DEEPEN/BROADEN/PIVOT/CONCLUDE decision.
- `pivot` — material change in research direction.
- `report` — human-facing progress report generated.
- `pause` / `resume` — interrupt-safe state transitions.
- `conclude` — final decision and archive.
