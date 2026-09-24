# N1V approved execution protocol

User approval: “批准 N1V 方案并继续 GPU2 实验（建议）”.

The approved proposal `n1v-bounded-recovery-proposal.md` remains immutable (SHA fc7f573af4c7a3cd5a8e5ec273ba03c5f3a6f0b605ceb1fd420094a770c83e99). Its pending-approval label is historical; this approval supersedes it. Authority: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/resource/n1v-approved/authorization.json`, SHA `531c66107cafe3ad650b974f459f0f4a3ddc085042dd8354d7e59b562af87015`.

Both worktrees share250attempts/48GPUh, caps baseline13/development124/validation60/formal40/recovery13, protected14+10GPUh. Snapshot114attempts/16.081373450989588GPUh leaves30primary and6recoveries,7.918626549GPUh before protection. Earlier GPU3 authority at06:30 is superseded by this latest explicit approval; do not resume its queue. No old terminal or costs are rewritten.

N1V uses30new task-interleaved cells: task-even Q0,C0,N1; task-odd C0,Q0,N1. Same frozen Dev seeds, task inputs, RDT1B,176candidates/11batches, Stage180s, one application invocation per query. The sole N1 change remains target-distance × positive-gripper-command-duty descriptor. FirsttwoN1 cells are included implementation checks, not success screens.

Prospective recoverability requires a clean child exit with exact Stage timeout exception, incomplete timed-out Stage event, frozen configuration/task identity, reconciled observed cost subtotals, safe metrics, and empty GPU-Xid evidence. BadJSON/unknown/identity/cost/numerical failures are nonrecoverable. Failed-call token usage is UNKNOWN. Each originalcell may have one whole-episode retry, at most6total, identical seeds/source/initialization, explicit retry_of, charged recovery. A valid task failure is retained and never retried. Completed cells survive administrative queue interruption. No other mechanism, search or Stage policy change is authorized.

N1>=5/10 and >=same-roundC0/Q0, complete10validcells and observed QD activity are required before the original independent validation/formal gates. Otherwise report incomplete or not-adopted. Full development expected6–8hours plus resource/recovery delays, subject to protected GPU budget.
