# Prospective E2 transport and N7 tracking measurement (proposal; inactive)

Status: **CPU implementation ready, no E2 GPU dispatch authorized yet**. The
prior passive diagnostic's task0 is valid; task3 is invalid under its frozen E1
transport gate. Neither is relabelled. Task6/9 were not run. The stopped report
is `passive-diagnostic-stopped-v1.md` (JSON SHA-256
`ca5bb714dfca5d4ef8aa7322eb639087472e42612d2923aa7e80a52ef437c744`).

## Transport change and exclusion boundary

E2 is opt-in `allow_recovered_error_events=true` in `core/codex_stage.py`,
isolated commit `e757ed1` and dormant owning-worktree commit `f552638`. The
default E1 behavior is byte-for-byte preserved in the existing lifecycle
tests. E2 accepts a Codex stream with `error` events or completed `error`
items **only** if all of them occur after the single `turn.started` and before
the single nonempty completed agent message, which in turn precedes the single
`turn.completed`; usage must be complete, stream JSON valid and bounded, and
process exit zero. It records error-event/item counts and an accepted-recovery
flag. Any error after the final message, missing or multiple turn/message,
missing usage, nonzero exit, timeout, other tool item, or malformed event stays
fatal. The ordinary Stage answer parser still has to accept the final text.
E2 does not change model, prompt, images, timeout, application attempts,
gripper trigger, Stage rules, guidance, RDT/QD/ED, or credentials.

The observed invalid task3 E1 call at global step24 had seven `error` events,
one completed `error` item, one final agent message, one completed turn with
full usage and exit zero. Its final text said stage1/guidance-no, as did the
valid historical task3 call at the same step; E1 discarded it and applied
stage1/guidance-yes fallback, causing action divergence. This is a **read-only
Dev observation**, not retrospective E2 acceptance. It supports testing E2
prospectively, not assuming task success.

## Frozen scientific identities to instantiate after budget approval

Create a new four-cell `N7_E2_PASSIVE_TRACKING_DEV_20260928` plan under this
variant. Use exactly original N7 Dev tasks 0,3,6,9 in that order, seed/init
row/BDDL and N7 profile copied from
`artifacts/continuation_20260925/n7-dev-v1/plan.frozen.v1.json` SHA-256
`9cef973dd2a2f7cd07f82eb1965b96e2bcb3557f372e25dc4cd04dc622b277be`.
The N7 profile SHA-256 is
`d77b8472364cd00dc2548e9e8160672a4f16335a56736cf66d77de6ae74ccb2d`.
Bind the new source commit, E2 flag, runtime inventory, dataset hashes and
plan SHA before dispatch. Physical GPU3 only, one worker, Dev split only;
validation/formal closed. Four primary attempts at most, 1,800-second per-cell
timeout plus 40-second cleanup, 4.2 GPU-process-hour local ceiling. No
automatic retry. Stop on invalid native evidence, Stage condition, tracker
snapshot, GPU identity or budget. An invalid task outcome is reported and does
not justify retesting the same cell for selection.

This entire cohort uses E2, including task0; do not mix its performance score
with the E1 partial diagnostic. Every cell must have SHA-verified native
evidence and the same passive keypoint snapshot introduced at `9d30070`.
Report target0 tracking validity and stable tracker instance/generation at
each adjacent guided chunk; target displacement threshold stays 0.01 m.
For the feedback-conditioned QD branch, require at least two **scientifically
valid distinct task episodes** with tracked target shifts, at least two
immediate same-stage next guided opportunities with stable tracker identity,
and a candidate behavior represented in physical coordinates across chunks.
If any cell fails the frozen transport/evidence gate, stop this cohort; do
not use that invalid cell to pass the mechanism gate. This diagnostic alone
cannot promote an algorithm.

If the gate passes, write and CPU-test one specific cross-chunk physical
feedback candidate before freezing a matched four-arm Dev comparison
(C0/Q0/N7/candidate) on all four exposed tasks. Freeze controls, order,
source, config, metrics and stopping rules before online testing. A second
candidate must address a distinct mechanism and receive a separate frozen
comparison. Fresh validation and historical formal remain protected as in
the original execution specification. The expanded numerical limits are in
`../../budget-extension-proposal-20260928.md` and remain inactive until the
user approves them.

CPU preflight now: 67 tests in `tests/test_codex_stage.py` and
`tests/test_codex_stage_lifecycle.py` pass, including the observed seven-error
event shape and default E1 parity. No live Codex or GPU call was made for E2.
