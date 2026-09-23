# Stage JSON schema repair and common N1S cohort — 2026-09-23

N1R Q0task0 completed720steps in629.09527898seconds, valid task failure. N1R
C0task0 had a completed Stage call atstep320 whose51-token response omitted
the required output fields; parsing failed after35.23007907seconds. This was
not a timeout or GPU failure. The query and all observed usage remain logged.
The owned queue was stopped after detecting invalidity; the attempt ending
fc39e13b4f1d is aborted/KeyboardInterrupt/outcome_valid=false,546.607421451seconds,
with344environment steps. Do not reclassify or retry this identity. N1R closes
INCOMPLETE_STAGE_FORMAT_FAILURE,1/30valid,2dispatched. Its Q0 failure and C0
invalidity are retained and cannot be pooled into a repaired cohort.

The installed Codex0.155.1 help and official documentation describe
--output-schema for constraining the final response to a supplied JSON schema:
https://learn.chatgpt.com/docs/non-interactive-mode#create-structured-outputs-with-a-schema

Explicit new transport format json_schema_v1 requires exactly stage(integer>=0),
guidance(enum yes/no), evidence(nonempty string validated locally). All fields
are required, additional properties forbidden, duplicate keys/type errors
rejected. Preserve the raw JSON and observed usage even on error. Decode only
validated JSON to the existing three-line parser, preserving the original
stage clamp, boolean mapping and decision rules. Keep original user prompt
and image bytes/order. The developer format instruction explicitly supersedes
the prompt's three-line formatting request. This formatting change can affect
model outputs, so it is a disclosed common condition, not an old-condition
retry or proof that previous predictions would match.

Keep gpt-6-astra/low,managed ChatGPT login,90second call timeout,single logical
attempt,no tool/skill calls,CLI binary identity,HTTP-counter uncertainty and
all token accounting. Default legacy_text and its public policy hash remain
unchanged. Freeze output format/schema in the new public policy hash, runtime
override, observed transport and label codex_login_astra_low_json_v1. No broad
fallback that guesses stage from malformed prose, no query retry.

Before GPU dispatch: test malformed real-response regression, missing/extra/
duplicate fields, strict types, usage retention, legacy behavior, and frozen
runtime binding. Then make exactly3 accounted CPU-only live calls using fixed
synthetic images and Stage descriptions; test format/usage completeness only,
not robotic accuracy. No GPU/model/simulation calls in this connectivity test;
record source/config/schema identity and every success/failure/token cost.
Stop if any live call fails; do not loop until it passes.

After those checks, freeze N1S,30development cells, same original Dev seeds,
task/init rows,weights,720steps/1800second ceilings,ED/QD budgets,trace settings,
GPU2-only binding and order as N1R: paired C0/Q0 controls20 then N1tasks0..9.
All three arms receive this identical Stage-format repair; N1 still differs
from Q0 only in target_distance_gripper_duty_v1. The first two N1 cells remain
implementation checks within its10cells. Any invalid/infrastructure result
stops the queue; valid task failures continue. In this opt-in JSON condition, any
failed Stage query first persists its event, then raises through the existing
episode error handler, saving video and compute/usage before queue invalidation. No automatic dispatched retry.
No old cell substituted; runtime diagnostic and N1R results reported separately.

At repair admission, shared totals17attempts,11development consumed (including
one in-flight parent-worktree GPU3 diagnostic), about
1.7034GPUhours. Preserve240attempts/48GPUhours,100development ceiling and
14validation+10formal reserved GPUhours. N1S consumes30 of the remaining89
development slots; later N2/H branches remain conditional on evidence and
actual remaining budget, with no expansion. Validation/formal stay undispatched.
Dev promotion remains N1>=5/10 and >=same-roundC0/Q0 with validity and actual
mechanism use. No claim of improved scientific performance from this repair.
