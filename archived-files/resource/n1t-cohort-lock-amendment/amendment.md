# N1T resource scheduling amendment

The original queue690225 waited about20minutes before its first episode and again
between completedQ0task0 andpendingC0task0 because another worktree holds the
shared runner lock across multiple episodes. It was stopped only while waiting:
no N1T GPU attempt was active; one valid Q0failure is preserved. No episode was
aborted or retried. Original plan490e5d0 andsourcea5a65c4 remain unchanged.

The hashed artifact wrapper obtains the same existing runner lock, then holds it
across the remaining29 original keys. Only nested requests for that same lock in
the same PID are reentrant. State/admission locks are unchanged; PID/inode changes
fail closed. An unresolved shared execution journal prevents a new cohort lease.
Another existing lock owner finishes naturally before acquisition. Exactly one
GPU worker andphysicalGPU2, original5secondpoll/120secondidle, originalbudget and
invalidity-stop rules remain active. SIGTERM uses the original supervised stop
path; all exits release the lease.6 CPU tests verify contention, symlink alias,
state-lock exclusion, exception restoration, PID andinode guards. This is resource
scheduling provenance, not a new scientific cohort or transport condition.

Manifest binds the originalplan hash, exactwrapper hash, tests andsuffix. The
originalqueue log/status remain intact. All GPU dispatches still occur through
unmodified frozenqueue/runner admission andaccounting. Do not edit wrapper,
manifest, source orplan while the newqueue is alive.
