# Passive Stage lifecycle observation

This isolated change is based on frozen `f6a9ab04c0f184bbe2f8c837b33492835bc8fec9`.
It adds diagnostic observations only. It authorizes no online run, retry, new
timeout, recovery, or change to any historical result. The original N4 record
and its unavailable usage remain unchanged.

`core/codex_stage.py` keeps the original command, environment, PNG/prompt input,
regular stdout/stderr temporary files, single `communicate(timeout=...)`,
owned-process cleanup, parser and counters. The 90-second default and public
invocation policy are unchanged. On timeout it still cleans up, parses available
output for accounting, and unconditionally returns the original timeout failure,
even if one valid response and complete usage were observed. The unchanged
function and source hashes are in `validation-v2.json`.

The new `core/codex_stage_lifecycle.py` samples a duplicate of the stdout descriptor with
`os.pread` on a diagnostic thread, without seeking, changing its offset, taking
over a pipe, signaling a process, accepting responses or updating counters. It
uses the same four-MiB stream bound and records at most 4096 observations. Its
10-ms polling interval is not a scheduling-latency guarantee. Normal finalization
stops and joins the thread before the temporary files close. The worker owns and
closes its one duplicate descriptor; it never reads a subsequently reused
original descriptor. Each join is bounded at 50 ms. If it times out, the public
snapshot is frozen as incomplete and this process permanently disables new
observers (`prior_observer_timeout` on later calls), while normal provider calls
continue. A process-local semaphore also permits at most one observer at once.
A permanently blocked OS read cannot be forcibly interrupted by a Python
thread: at most one daemon observer and its one private descriptor could remain
until process exit. If the read returns, it performs no further reads and closes
the descriptor. Normal/error/temporarily blocked cases are tested; permanent
kernel blockage is a limitation, not a proven cleanup success. Both production
files must be included in a future frozen source inventory.

The additive `last_result.transport.lifecycle` object has schema
`codex-stage-lifecycle-v1`. It records monotonic request/spawn/communicate,
first-byte, completed-turn, complete-usage, timeout, cleanup and exit-observation
times; return code; observation completeness; and bounded event records. Allowed
event kinds are thread/turn/item lifecycle kinds and error; other kinds are
`other`, invalid JSON is `invalid_json`. Item kinds are only `agent_message`,
`reasoning`, `error`, or `other`. Error categories are fixed local labels. Agent
message text, reasoning text, remote error text, stderr, prompts, argv,
environment values and credentials are never copied into this new object.
Existing original response/usage fields and counters retain their old semantics.

Times mean **local file observations**, not remote generation or arrival times.
Several records read together can have the same time. A final line without a
newline is classified only in the final drain. The exit time means the already
reaped return code was observed after observer finalization, not the exact OS
exit instant. A completion observed before timeout is evidence only of that
local observation; a later observation does not prove it was absent earlier.
`complete_usage_observed` means at least one completion with the original three
required integer usage fields was seen; it does not establish exactly one turn,
stream validity, response acceptance, HTTP attempts, or unreported usage.
Absent timestamps remain null when the observer was constructed; construction
or snapshot failure supplies only schema/incomplete/error fields and the other
fields are unavailable. A no-throw facade isolates construction, each marker,
startup, finalization and snapshot access. Observer failures and limits set a
fixed category and incomplete observation, preserving original transport
results and counters. Observations are attached to the ordinary
returned Stage event; an abrupt loss of the containing Python process before it
returns can still lose these observations. There is no separate durable live
log or additional writer.

The final focused CPU test command/results are in `validation-v2.json`: 25
existing transport tests plus 30 new tests. A hash-pinned copy of the original source is the differential
oracle for success, empty/malformed/multiple events, missing usage, unexpected
items/events, nonzero exit, startup/I/O errors, oversize streams, and timeout
with no/partial/completed output or completion during cleanup. Stable public
results, counters, prompt, command and environment match exactly, excluding
existing elapsed-time fields and the additive diagnostic. Five real local
children additionally check ordering, including completed-before-timeout and
SIGTERM-handler completion during cleanup; none invokes Codex or an API. A real
child tree verifies the existing outer process group, owned cleanup and an
unrelated process remaining alive. Other tests cover file-offset preservation,
no text leakage, byte/event bounds, diagnostic failures and no observer thread
remaining in tested cases. Fault injection at construction, after-spawn markers,
finish and snapshot access confirms original success/counters and continued
communication. A deliberately blocked pread verifies bounded return, immutable
snapshot, process-local disable without failed-call increment, and eventual
thread/descriptor cleanup after release. These CPU checks do not prove identical remote scheduling or zero
observer overhead; elapsed request cost continues to include that overhead.

The first implementation lacked isolation for all hook failures and used an
unbounded join. Independent source/fake review reproduced those defects before
any integration or online use. Its two exact source files and initial 50-test
record are retained under `initial-review/` as superseded evidence only. That
initial test pass did not cover the defects and is not the final acceptance
record. The amended implementation does not change the original Stage rules.
