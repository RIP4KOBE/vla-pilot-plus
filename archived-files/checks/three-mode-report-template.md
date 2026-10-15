# Three-mode steering evaluation

Status: **Pending all three complete cohorts and full v2 audit gates.**

Frozen source commit: `33954ead452927fc3168efb610487a688f89169e`.
Each mode uses tasks 0–9 and seeds 44, 235, 43, 546, 6, 621, 197, 87, 151, 548.
VLS, EDS and EDS+QD share online Stage and fresh reward generation. They have
different actual compute budgets; record the observed counters below.

| Mode | Valid tasks | Validated success count | Success task IDs | Stage queries / errors | Guided chunks | Model calls / batch rows | Reward evaluations | Wall time | GPU / EGL |
|---|---:|---|---|---|---:|---|---|---|---|
| VLS | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | 1 / 3 |
| EDS | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | 0 / 2 |
| EDS+QD | Pending | Pending | Pending | Pending | Pending | Pending | Pending | Pending | 4 / 6 |

Fill each validated cohort score only when `runs[mode].accepted` is true; leave
running cohorts pending. Report `all_cohorts_valid` separately from
`integration_acceptance`. The integration gate additionally requires EDS >= 3/10;
`final_accepted` aliases this combined gate. Valid EDS 2/10 remains a valid, visible
result and fails only the integration performance threshold. Preserve such a
result; this reporting helper never initiates reruns.
A task's unsuccessful environment outcome is scientifically valid when its
contract and mechanism audits pass. Never infer validity from success alone.

Record the exact run directories, cached audit SHA256, fresh read-only audit
result, common source-file mapping SHA256, asset and RNG identities, shared
protocol identity, per-task videos, timings and compute fields from the JSON.
Counter `total: null` means unknown; `observed_subtotal` must not replace it.

The QD mechanism report distinguishes recorded archive reconstruction from
independent descriptor geometry or executed-tensor verification. Each archive
is fresh per chunk. This experiment does not demonstrate recursive or
cross-chunk self-improvement. A single seed per task does not establish causal
superiority of a method. Device and provider variation remain documented.

The EDS >= 3/10 threshold is an integration acceptance criterion, not a
statistical non-inferiority claim or proof that online stochastic runs will
always match that score.
