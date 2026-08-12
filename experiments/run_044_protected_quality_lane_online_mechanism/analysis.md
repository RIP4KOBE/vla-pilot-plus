# Analysis — Run044 protected-quality lane online mechanism

Classification: `VALID_SCIENTIFIC_MECHANISM_FAIL`

Decision: `CONCLUDE_H5_V5_ONLINE_MECHANISM_FAIL_NO_ADOPTION`

## Exact execution and task result

User-authorized recovery protocol `5da58a0` preceded runner implementation
`c071a76`, immutable recovery manifest creation, health, GPU admission and IDs
95–98. The manifest is mode `0444`, file SHA-256
`8e8b5ec5b467275a647b70f7facdbf41407bfcabcd644d2925dfa096bc129652`
and payload SHA-256
`f472b63e96367d444ef3a134ec531a5e934951d3b059269f5538902522e93060`.

Both jobs completed validly on admitted GPUs 4/5. Their metadata independently
verified the repaired backend execution identity:

```text
episode 0: task 5 / seed 666847
episode 1: task 7 / seed 87603
```

Control and candidate each scored `0/2`; both tasks in both profiles were
classified `timeout without completion`. Delta is zero, with no gained,
retained or lost task. Candidate diagnostic gap to five is five. This mechanism
stage therefore supplies no task-level success gain and does not change the
historical formal best/gap of `2/10` and `3`.

## Mechanism and hard-gate result

Control passed its metric gate: 56 records, QD/secondary inactive, no fallback,
nonfinite, mask or qpos violation. Candidate produced 41 valid records with
410 global-quality anchor activations and 1,685 protected-secondary parents:

| Task | Records | Anchor activations | Secondary parents |
| ---: | ---: | ---: | ---: |
| 5 | 38 | 380 | 1,573 |
| 7 | 3 | 30 | 112 |

The candidate had 410 QD iterations. Secondary selection was positive in 407,
but exactly three iterations had zero secondary parents:

- task 5, global step 40, iteration 2;
- task 5, global step 168, iteration 0;
- task 5, global step 216, iteration 2.

Protocol-v1 hard gate 4 requires positive secondary selection in every
candidate iteration. These three observations are real online mechanism
failures, not missing telemetry or an audit schema defect. Aggregate activation
cannot override the preregistered per-iteration gate. The immutable audit is
mode `0444`, file SHA-256
`57544a8226b00fbf8085a4944a11d4908709be754990fcbce416b241f21c1cc9`;
its only hard failures are the three zero-parent identities above.

All other measured gates passed: exact task identity, control metric contract,
task noninferiority/retention, zero disallowed safety outcomes, zero fallback,
finite/mask/qpos safety, artifact validity and attempt accounting. Candidate
selection latency P95 was `2.730221 s` versus control `2.610942 s`, ratio
`1.045684 <= 1.25`.

## Accounting and conclusion

- Append-only ledger SHA-256:
  `ac1a7713487d19e372d05b0d5649a8345fff09960b73397c657c75c2c650f8d0`.
- Original invalid IDs 91–94 remain aborted and inadmissible.
- Scientific IDs 95–98 are the only active recovery cells.
- Global reservations: `98/144`.
- Effective online episode attempts: `70` cumulative (`+4` in Run044).
- Run044 recovery GPU use: `1.2104288889` hours.
- Cumulative GPU use: `6.9468320556/48` hours.
- Per-job and complete Run044 credential audits passed; credential material was
  not serialized. Formal episodes remain zero.

Under the frozen valid-FAIL rule, H5-v5 ends without Dev-A, validation or formal
evaluation. The protected lane preserves quality and activates heavily, but it
neither produces a task gain nor maintains the required universal secondary
availability. No gate relaxation, outcome-driven rerun or sixth candidate is
authorized.
