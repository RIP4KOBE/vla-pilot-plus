# Prospective reconnect-event contract and N1T cohort — 2026-09-23

N1S closes INCOMPLETE_STAGE_EVENT_FAILURE: 8 valid task failures (C0 0/4,
Q0 0/4), 1 invalid Q0 task4, and 21 undispatched cells. N1 is untested.
The ninth attempt c19f2bba8e77 stopped at step432 after697.407583267 seconds.
Its failed Stage call returned schema-valid JSON and one complete usage/turn,
but an additional top-level error event was rejected. The error message and
process return code were not retained. Its cause is UNKNOWN; do not retrospectively
call it a recoverable reconnect, change its terminal ledger, or retry that identity.
All previous data and shared costs stay visible. No previous cell is substituted
into N1T, and the eight failures are not evidence about N1.

Official event documentation lists error and turn.failed separately from turn.completed:
https://learn.chatgpt.com/docs/non-interactive-mode#make-output-machine-readable
It does not establish the missing historical error's meaning. The pinned0.155.1
binary contains the literal Reconnecting... marker. The new rule below is our
explicit prospective acceptance contract, not a claim that all CLI errors recover.

## Local transport change only

Default strict_v1 remains unchanged. New opt-in completed_reconnect_v1 requires
json_schema_v1. Accept only an error message with exact numbered prefix
Reconnecting... n/m (1<=n<=m<=999), optional space/newline detail, occurring after
one turn.started and before its agent message and turn.completed. All other
error events, forbidden items, failed/missing/multiple turns, missing/invalid
usage, duplicate/malformed schema fields, timeout and nonzero process exit still
fail. There remains one application invocation; no application query retry.
The successful call must have exactly one response, one complete usage, one
completed turn and zero process exit. Record process return code/timeout even
when event parsing fails. Persist safe error classification, ordinal counts,
message length and SHA256; never persist raw potentially sensitive server text.

The CLI path/binary0.155.1, managed login, model gpt-6-astra, low effort,
90second ceiling, tool restrictions, user/developer prompt, image bytes,
JSON schema and all actual CLI arguments are unchanged. The local acceptance
contract gets a new public policy hash and label
codex_login_astra_low_json_reconnect_v1. All C0/Q0/N1 receive it equally.
The system's default codex now reports0.156.1, but the experiment keeps the
previous absolute0.155.1 binary and verifies its existing SHA before dispatch.

## Verification and bounded continuation

299 focused CPU tests passed.93 clean N1S calls were reconstructed from their
recorded event types, agent JSON and complete usage: old/new parsers give identical
normalized decisions and accounting. This is not byte-for-byte raw-stream replay;
the one failed call cannot be replayed because its error payload is missing.
Existing3 synthetic live schema calls remain evidence for the identical CLI
request format only. No new live call is needed for this local classifier;
reconnect behavior is tested with synthetic event streams, not claimed observed
in the old failure. See analysis/n1s-stage-event-failure under owned artifacts.

Freeze N1T30 development cells, C0/Q0/N1 each10. Preserve N1S original task order,
paired Dev env/policy seeds, init rows,720steps/1800seconds, search176/11 budget,
weights, caches, N1 descriptor, mechanism traces and GPU2/EGL1. Controls20 first,
then N1 tasks0..9; first2 N1 remain implementation checks, not success screening.
No source edits after dispatch. Valid task failures continue; invalidity stops
for review. This authorizes one complete new-condition cohort, not repeated
cohort restarts until a favorable result. No old identity is retried or relabeled.

Maintain global240attempts/48GPUhours,100development ceiling,60validation and
40formal reserved slots plus14+10 reserved GPUhours. At review31attempts have
been dispatched (development25 including another worktree's in-flightGPU3cell),
with4.0141completed GPUhours plus in-flight cost. All30 N1T attempts count.
Other-worktree shared attempts reduce remaining capacity; inspect the journal
before each dispatch and do not expand the budget. One shared worker, resource
poll5seconds,120second stable idle, physicalGPU2 only; never stop the other GPU3
worker. This is a transport correction, not an additional QD mechanism search.

Promotion stays N1>=5/10 and >=same-round C0/Q0 with validity and substantive
mechanism activity. Only then validation20/arm (>=10/20 and >=controls), then
formal10/arm (>=5/10 and >=controls). No validation/formal launch before gates.
If N1 fails Dev, only the already-prespecified evidence-supported N2 or H route
may be considered subject to actual shared remaining budget. No stacking or
Stage/FSM retuning inside this cohort. Never claim the formal target achieved
from CPU checks, Stage predictions, partial controls or this engineering repair.
