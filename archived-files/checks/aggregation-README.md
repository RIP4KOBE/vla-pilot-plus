# External read-only aggregation

`aggregate_steering_cohorts.py` is an external reporting tool. It is outside the
frozen runtime and never writes inside the raw run directories. It loads YAML
and JSON, hashes frozen snapshots, and summarizes recorded evidence. There are
no model, simulator, GPU or provider calls.

Use the same CPU Python environment as the frozen cohort. Example from the
repository root:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 \
  /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  .worktrees/exp/steering-integration/checks/aggregate_steering_cohorts.py \
  --output-prefix .worktrees/exp/steering-integration/checks/three-mode-final
```

Defaults select `runs/{eds,vls,eds_qd}-common-20261013`. `--runs-root` and
`--suffix` are explicit overrides. Outputs are `<prefix>.json` and `<prefix>.md`;
existing outputs are refused unless `--replace` is explicitly supplied. Output
paths inside the runs root are always refused. Exit 0 means integration acceptance;
exit 2 means partial or integration not accepted. Inspect the separate validity
and performance fields for the reason.

Running cohorts remain partial. A completed cohort must have an unchanged source
snapshot, correct full10 task/seed protocol, finished/exit0 status, valid full v2
cached audit, valid hashed detail reports, and a fresh `audit_steering.py
--no-write` audit. Before that subprocess, all current Python files listed in the
frozen source manifest and the configured RNG fixture manifest are hashed. The
subprocess has CUDA hidden and bytecode writes disabled. It does not run a worker.
The current offline auditor must match the recorded frozen source; a different
current checkout fails closed rather than silently substituting another auditor.

Cached and fresh outcome/check summaries must agree. The fresh reconstruction's
canonical hash must match the saved method-detail JSON. Task reports contain a
new generation timestamp on recheck, so their cached file hashes are verified
and their task validity/outcome/check summaries are compared semantically. Final
success counts come from the fresh report. Source mappings, model content,
normalization, LIBERO/RNG identity, imported dependencies, provider identity and
shared protocol must match across all modes. Only enumerated intentional method,
GPU and machine/output path differences are excluded.

`test_aggregate_steering_cohorts.py` uses synthetic completed bundles and a stub
revalidator to test gates, including forged cached scores, incomplete tasks,
changed assets/source/RNG/protocol, stale method details, and unknown counters.
These fixtures are tests, not scientific results. Real running-cohort validation
is stored separately in `three-mode-partial-validated.json` / `.md`.

`all_cohorts_valid` means all three complete cohorts passed their protocol and
mechanism gates and shared-contract checks. `integration_acceptance` additionally
requires the valid EDS cohort to achieve at least 3 successes out of 10, matching
the recorded reference threshold. `final_accepted` is an alias for
`integration_acceptance`, so older callers cannot treat a valid EDS 2/10 as
integration acceptance. The explicit `performance_gate` records threshold,
validated EDS score and pass/pending.

Completed valid scores remain visible in `runs[mode].final_successes`,
`comparison.validated_cohort_success_counts`, and the Markdown table. When all
cohorts are valid, `comparison.final_success_counts` is populated even if EDS is
2/10 and integration is declined. Running cohorts keep those scores null/pending.
A failed performance threshold never changes scientific task/cohort validity and
does not trigger reruns; preserve the result for attribution and review.

The EDS >= 3/10 threshold is an integration acceptance criterion, not a
statistical non-inferiority claim or proof that online stochastic runs will
always match that score.
