# Protocol v3 — Run044 exact identity recovery after +1 cap authorization

Status: `LOCKED_AFTER_USER_BUDGET_AUTHORIZATION_BEFORE_RECOVERY_RUNNER_OR_EXECUTION`
Date: 2026-08-12
Parent protocol commit: `0e59987011ed29779bd621a856283c8746a6b5df`
Identity-repair protocol commit: `5f94fd45ef94594dd21bb1d3bae802fb23a516c9`
Identity-repair implementation commit: `fd1a5f3`
Incident result commit: `a316ca1`

## Explicit authority and narrow budget change

The user explicitly authorized the requested recovery on 2026-08-12. The
global reservation cap changes from `143` to `144` solely so all four exact
Run044 recovery cells can be reserved. This is the only budget change:

- prior append-only global reservations: `94`;
- exact recovery attempt IDs: `95–98`;
- post-recovery global reservations: `98/144`;
- conservative prior GPU use: approximately `5.73640/48` hours;
- formal budget and authorization: unchanged at zero/false.

The extra reservation cannot be reassigned to Dev-A, validation, formal, a new
candidate, a retry after a scientific failure, or an outcome-dependent rerun.
The v5 worst-case total is now exactly 144 rather than 143.

## Frozen scientific identity

The recovery repeats the original four cells and no others:

| Profile | Task | Seed |
| --- | ---: | ---: |
| `p2_stage_on_abs_rbf_control` | 7 | 87603 |
| `p2_stage_on_abs_rbf_control` | 5 | 666847 |
| `eds_qd_protected_quality_secondary_v1` | 7 | 87603 |
| `eds_qd_protected_quality_secondary_v1` | 5 | 666847 |

The runner must pass the backend-sorted execution schedule
`[(5,666847),(7,87603)]` while verifying metadata by task identity against the
frozen pairs `[(7,87603),(5,666847)]`. Algorithms, source hashes, profiles,
checkpoint, runtime cache, DINO seed, task suite, perturbations, horizon,
compute contract, mechanism gates, task-retention gate, latency/safety gates and
decision rule remain exactly those in protocol v1.

## Authorized runner and immutable recovery manifest

Before execution, only these tracked files may change:

- `scripts/eds_qd_autoresearch_v5_runner.py`
- `tests/test_eds_qd_autoresearch_v5_runner.py`

The implementation must preserve and hash-check the original immutable manifest,
the append-only ledger through the identity-abort event, and the incident archive.
It may add recovery-specific manifest/reservation/dispatch/audit support but may
not rewrite any existing ledger row or incident file. Dedicated tests must prove:

1. exact IDs 95–98 and cap 144 accounting;
2. original IDs 91–94 remain aborted and scientifically inadmissible;
3. task-sorted seed binding yields the frozen task identities;
4. recovery requires a new immutable manifest and fresh health/GPU admission;
5. only active recovery IDs contribute to the scientific audit;
6. no credential material enters command, manifest, ledger, output or Git.

After the runner commit, freeze one new mode-`0444` manifest at
`manifests/mechanism_recovery_v2_manifest.json`. It must bind this protocol and
runner commit, original manifest hashes, final pre-recovery ledger hash
`447ac12776cc882024450d4e3a9166c46bd3318259ef574c90be5c7e43562371`,
incident archive hashes, exact cells/IDs, source and dependency hashes, budget,
and `formal_authorized=false`. The original manifest remains untouched.

## Fail-closed transaction

The transaction order is recovery-manifest/source/artifact/write-boundary/storage
validation, runtime-only credential health, fresh two-snapshot GPU admission,
append-only reservation of IDs 95–98, append-only recovery dispatch, execution,
identity validation, audit and immutable result preservation. A failure before
reservation consumes zero IDs. After reservation, no further Run044 recovery is
authorized. Only owned Run044 processes may be stopped; no external process may
be preempted or co-located.

All protocol-v1 online hard gates remain unchanged except their accounting fields
must require recovery IDs 95–98, original aborted IDs 91–94, and global
reservations `98/144`. Partial incident data remain excluded. A valid PASS alone
authorizes a separate Dev-A protocol; a valid FAIL concludes H5-v5 without
Dev-A/validation/formal or a sixth candidate. Historical formal best/gap remain
`2/10` and `3` until independently changed by a later authorized formal result.
