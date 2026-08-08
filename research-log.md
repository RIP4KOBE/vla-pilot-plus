# Research Log

Chronological, append-only record of research decisions and actions.

| # | Date | Type | Summary |
|---:|---|---|---|
| 1 | 2026-08-08 | bootstrap | Audited baseline commit `5b0898e53d5b9e16200c17479a74746071215787`, design/report checksums, read-only decision manifest, raw audit/metrics, qualitative contact sheets, QD core/config/runner/audit code, and the Grid5 traceback. Historical decision remains `no_adoption_keep_p2_stage_on_abs_rbf_control`: control 3/10, uniform 0/10, sparse 2/10. |
| 2 | 2026-08-08 | bootstrap | Created branch `exp/eds-qd-autoresearch-libero-swap-ood` and its isolated worktree from the explicit base commit. Excluded and preserved the source worktree's unrelated untracked search-budget design. |
| 3 | 2026-08-08 | bootstrap | Ran the existing CPU-only QD archive/runner/audit suite: `56 passed in 3.22s`. Initialized autoresearch state in planning-only, paused mode. No GPU, LIBERO episode, storage mutation, or scheduled continuity loop was started. |

## Entry types

- `bootstrap` — scoping, baseline audit, literature survey, initial hypotheses.
- `inner-loop` — protocol, run, result, and keep/revert decision.
- `outer-loop` — synthesis and DEEPEN/BROADEN/PIVOT/CONCLUDE decision.
- `pivot` — material change in research direction.
- `report` — human-facing progress report generated.
- `pause` / `resume` — interrupt-safe state transitions.
- `conclude` — final decision and archive.

