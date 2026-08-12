# Run 033 analysis — online global-quality-anchor mechanism

Date: 2026-08-12  
Decision: `KEEP_H4_V3_ONLINE_MECHANISM_PASS_AND_AUTHORIZE_DEV_A_PROTOCOL_ONLY`

## Outcome first

Run 033 passes every frozen mechanism, task-retention, safety, latency, accounting, artifact and credential gate. On paired LIBERO-PRO `libero_object_swap` tasks `[3,8,9]`, the contemporaneous control scored `0/3` and `eds_qd_global_quality_anchor_v1` scored `1/3`. The candidate gained task 9, lost no control-success task, and therefore supplies a direct `+1` target-linked signal rather than proxy-only progress.

This does not establish the `>=5/10` target. The mechanism subset leaves a diagnostic gap of 4 to five successes, while the historical formal best remains `2/10` with gap 3. Formal evaluation remains forbidden. The PASS authorizes only a separately committed Dev-A protocol on the already frozen six unseen tasks/seeds.

## Task-level results and failures

| Task | Control | Candidate | Delta | Audited failure class |
|---|---:|---:|---:|---|
| 3 | fail | fail | 0 | both `timeout without completion` |
| 8 | fail | fail | 0 | both `timeout without completion` |
| 9 | fail | success | +1 | control `timeout without completion`; candidate completed |

Aggregate: control successes `[]`; candidate successes `[9]`; gained `[9]`; retained `[]`; lost `[]`; candidate-minus-control `+1`. No finer behavioral cause is asserted for tasks 3 or 8 because the frozen automatic taxonomy supports only timeout-without-completion here.

## Mechanism attribution

The candidate produced 110 valid chunk records. Every record used the active grid archive, causal envelope, sparse-priority allocation, exactly one global-quality anchor, no fallback, and the frozen `176 search / 176 QD / 11 score calls` contract. Across all records it logged 1,100 anchor activations and 751 real omissions rescued (`68.27%`):

| Task | Records | Activations | Rescues |
|---|---:|---:|---:|
| 3 | 17 | 170 | 114 |
| 8 | 89 | 890 | 624 |
| 9 | 4 | 40 | 13 |

The intervention therefore repaired the measured allocation omission online and, unlike the v2 exact-zero fallback, yielded one paired task success without a retention loss. However, 738 rescues on failed tasks 3/8 did not produce completion. Rescue frequency alone is not a success proxy; Dev-A must test whether the task-9 gain transfers across six unseen tasks instead of motivating anchor-count or threshold exploration.

## Validity, safety and cost

- Both jobs exited 0, produced 3/3 episode metadata and videos, passed strict perturbation/suite checks, and were marked valid by the runner.
- Control/candidate metric records were 43/110. Candidate and control mechanism gates both passed; accounting, final-selection, nonfinite, action-mask and gripper-qpos violations were zero.
- Disallowed safety outcomes were empty for both profiles.
- Selection-latency P95 was `2.818499 s` candidate versus `2.657710 s` control; ratio `1.060499 <= 1.25`.
- Recovery scientific device wall was `0.376144 h`. Including the preserved pre-episode DINO incident, cumulative study usage is `4.183103444444445 / 48 h`.
- Global reservations are `78/143`: IDs 67–72 remain aborted pre-episode infrastructure evidence; IDs 73–78 are the only scientific Run 033 cells. Six of 19 recovery slots were consumed, leaving 13.
- Run-root credential audit passed over 161 audit-visible files. A separate exact scan over the complete artifact tree and tracked worktree found zero copies of the approved credential. Generic matches were inspected and were only sklearn bytecode/test fixtures.

## Infrastructure incident and immutable evidence

The first dispatch failed before episode 0 because isolated runtime caches lacked the already audited local DINOv2 seed and `torch.hub` received GitHub HTTP 403. Protocol v2 `5e3ca98` preceded the runner-only repair `e1b4f3e`. No EDS-QD, task, seed, checkpoint, Stage, environment, evaluator or gate changed. Failed IDs 67–72 and their outputs/logs were preserved read-only; exact-cell recovery IDs 73–78 used the same matrix after fresh health and GPU admission on GPUs 2/4.

Immutable evidence:

- recovery manifest: `mechanism_manifest.v2.json`, mode 0444, SHA-256 `6364f4a04a49c75d99c695d7bf7e0c186949a20b44c4f44776437b7c019d07e2`, payload `cb9e7b1728b3dcf2215c09f49b2a44dd39fec153a9dd7f2903aa3b34d8f59647`;
- final audit: `mechanism_audit.json`, mode 0444, SHA-256 `b5f4c671d28bcec039f0b3ad6536ab1191fcad6c4f8c843926e66e3612acf96b`;
- final attempt ledger SHA-256 `b75aecccf0cd4301fd0f17f28f9d96dee2e2b84516911783381d390e43cb2fe6`;
- recovery run manifest SHA-256 `ed82e32fe7c806ea973d52399bff93c6dfdac69fd30073aa5e4e25f43b0ea1cd`.

## Next gate

Freeze and commit a Dev-A protocol before adding runner logic or reserving any cell. Dev-A must use only frozen tasks `[0,1,2,4,6,7]` and seeds `[307995,262892,731741,14859,648306,960581]`, pair control and the unchanged candidate, and require candidate `>=3/6`, at least `+1` over control, zero lost control-success tasks, plus unchanged validity/safety/latency/mechanism gates. A valid failure ends v3 with no validation or formal run; a PASS only authorizes validation protocol.
