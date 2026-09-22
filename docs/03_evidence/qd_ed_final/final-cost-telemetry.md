# Final observed cost telemetry

**TARGET_NOT_MET. Complete total calculation cost is Unknown.** Scope: the 11 attempt-ledger output directories only; standalone healthchecks/CLI probes and agent work are excluded. GPU hours remain in root accounting and are not recomputed here.

- Complete registered episode-counter windows: 1/11; missing in 10 attempts. Every attempt has outcome_valid=false. The complete window ended with execution_error, not task success.
- Observed DiT call attempts: 9; model batch rows 144; denoise invocations 3; scheduler steps 8; denoise step batch rows 128.
- Same episode window: reward function attempts 112, candidate evaluations 112, scoring batches 7; DINO forward attempts 1; text encoder 1; vision encoder 1. These are partial study lower bounds, not whole-study totals.
- Separate completed EDS records: 7 chunks / 70 iterations / 77 search-score batches / 1232 candidate rows / 70 recorded renoise iterations. Do not add candidate rows to reward-function call counts.
- Recorded EDS loop latency subtotal: 22.874936929s; initial sampler 4.455457352s. Those intervals overlap select-action timing and are not additive.
- Deduplicated completed fresh policy calls: at least 10, observed latency subtotal 36.902091575s; 1 recorded fresh-policy entry lacks an exit.
- Stage: observed 1 logical call, 1 completed turn, 0 recorded failed calls, 1 usage-complete call; 19.772138727s. Input 10800, cached input 0, output 42, reasoning output 0 tokens. This is the retained query subtotal plus the explicit zero-call episode window, not proof that all missing windows had no calls.
- Codex HTTP request/retry counts, whole-study component failures/latencies/tokens and monetary cost: Unknown. No missing field or absent file was converted to zero.

Evidence:

- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/attempts/rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0_r2__5621b7ebde96/eds_eval/eds_metrics.jsonl` (1 records).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/attempts/rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0_r3__6df33a24c65f/eds_eval/eds_metrics.jsonl` (3 records).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/attempts/rdt-qd-ed-final-20260921T093925Z__n1_dev_t00_q0_r3__6df33a24c65f/eds_eval/stage_events.jsonl` (1 records).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/attempts/rdt-qd-ed-final-20260921T093925Z__gpu6_native_c0_t00__6e57273c45b3/eds_eval/eds_metrics.jsonl` (2 records).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/attempts/rdt-qd-ed-final-20260921T093925Z__gpu3_native_c0_t00_r2__79342697c4d2/eds_eval/eds_metrics.jsonl` (1 records).
- `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/attempts/rdt-qd-ed-final-20260921T093925Z__gpu5_cuda_memcheck_c0_t00__66eec8a1ab74/eds_eval/episode_compute.jsonl` (1 records).

Ledger: `/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z/data/attempt-ledger.jsonl` (33 events / 11 terminal records; SHA256 7a503ba5f120d791598f3146d5e93bffaa523cd34656262a26854c73b84aad7a).

Per-attempt numeric projections, line references, hashes, phase timing sources and limitations: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/final-cost-telemetry.json`.

The historical `valid` ledger event is an accounting label here; it does not turn any failed or aborted sample into a valid result. No cost-per-success or method comparison is supported.
