# Protocol v2 — Run044 task/seed identity incident and fail-closed repair

Status: `LOCKED_AFTER_DISPATCH_IDENTITY_DISCOVERY_BEFORE_REPAIR_OR_ARCHIVE`
Date: 2026-08-12
Parent protocol commit: `0e59987011ed29779bd621a856283c8746a6b5df`
Runner implementation commit: `6bb5e91`

## Incident classification

The immutable manifest, credential health, two-snapshot GPU admission and IDs
91–94 reservation/dispatch succeeded. Before either job completed, the live
`episode_metadata.jsonl` exposed that LIBERO enumerates a filtered task set in
ascending task-ID order while the runner applied `episode_seed_schedule` in the
original unsorted protocol order:

```text
frozen:  task 7 / seed 87603; task 5 / seed 666847
actual:  task 5 / seed 87603; task 7 / seed 666847
```

The agent detected this from metadata, terminated only its owned Run044 process
group, and verified no owned worker remained. This is an execution-identity
infrastructure failure, not H5-v5 algorithm or task evidence. All partial
success/failure, video and proxy observations are excluded from every candidate,
promotion and target conclusion.

The first outer shell invocation had timed out before health completion and
created no ledger/reservation/process. It is not an attempt. The second invocation
created exact IDs 91–94 and those records remain append-only.

## Frozen evidence before repair

- Manifest mode `0444`, SHA-256
  `b6ae5091344aba325e1d5b698c8d19707e6aaf5aaef43ad5125721e423d1ff97`,
  payload `1f5374857469a8d00be00eb1562fcb8ed8b5b3d0ef11b3f3a08c1256a24773cf`.
- Initial ledger SHA-256
  `f057c7d7736a5c6fcf60ab41d3a70ad38b03a6f904a70631efbdd0033b5863ec`.
- Admission SHA-256
  `a3c4ccd9af5eec4a628b0eb3ba0d652ee3e6db9c7626e4753976f008bb56c70d`.
- Control: 20 partial metric records, two metadata rows, one partial fail video.
- Candidate: 30 partial metric records, one metadata row.
- Credential value/fingerprint was not logged. Logs contain only presence=true.

## Authorized repair

Before a repair implementation commit, only these existing files may change:

- `scripts/eds_qd_autoresearch_v5_runner.py`
- `tests/test_eds_qd_autoresearch_v5_runner.py`

The repair must:

1. derive the execution seed schedule by pairing the frozen task/seed map and
   sorting pairs by task ID, so the backend's actual ascending order yields the
   original exact pairs;
2. fail closed if frozen task IDs are not unique, lengths differ, or generated
   metadata order cannot equal `[(7,87603),(5,666847)]` by task identity;
3. append one immutable ledger event
   `dispatch_aborted_invalid_task_seed_identity` for IDs 91–94 without modifying
   their reservation/dispatch records;
4. support an exact-cell recovery ledger only after a future protocol explicitly
   supplies four new IDs and sufficient global budget;
5. keep candidate/control algorithms, task/seed pairs, profiles, gates and
   commands otherwise unchanged.

After the repair commit, partial outputs, logs, run manifest and admission may be
moved intact under the owned Run044 `incidents/invalid_task_seed_ids_91_94/`
root, accompanied by a path/size/SHA archive manifest; the original immutable
scientific manifest and append-only attempt ledger remain under `manifests/`.
No partial outcome may be summarized as task evidence.

## Budget stop boundary

Before Run044, global reservations were 90/143 and v5 reserved a maximum of 50
scientific cells, leaving exactly three recovery slots. IDs 91–94 consumed four
infrastructure reservations. Exact paired recovery requires four new IDs, but
only three are authorized. This protocol therefore authorizes zero new
reservation, GPU, API, model or LIBERO execution after repair.

Resumption requires either:

- explicit user authorization to increase the global reservation cap from 143
  to 144 solely for the fourth exact-cell Run044 recovery; or
- a user-directed conclusion with no recovery.

No runner repair, proxy activity, partial task outcome, available GPU time or
remaining wall-clock/GPU-hour budget can override this hard reservation boundary.
Formal remains unauthorized; historical formal best/gap remain 2/10 and 3.
