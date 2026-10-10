# Leaf 15.6: canonical STOP and frozen executable alias proof

This change is CPU engineering only. N36R2 release and admission remain disabled.
It grants no GPU, provider, simulator, source-adoption or execution authority.

`qd_ed_n36_stop.py` pins the exact lexical owner and relocated data STOP paths
from the explicit engineering contract, independently of checkout resolution.
The source-bound `n36-canonical-stop-v1` record identifies owner source
`ca4e6a96d049c7ebb1f302d755883388ddbfdbd8` and the unchanged deadline
`2026-10-11T11:13:13Z`. It is a veto binding, not an execution approval.
New draft/release plans must match this record and separately pass supported
checkout-layout validation. Callers cannot select a different pair.

The shared lstat guard rejects every entry (including dangling symlinks) and
all errors except missing entries. Admission, healthcheck reservation/start,
post-reservation, final worker launch, worker entry and pre-Main use it.
Next-dispatch goes through the same admission guard. Episode boundaries retain
1840 seconds of headroom; healthchecks require that plus their complete probe
and cleanup reservation. Canonical deadline clipping cannot be extended by a
caller. An entry may race a filesystem check; the child rechecks before Main.
STOP is never polled to signal an admitted episode. Settlement/context receipt
verification remains available after STOP and deadline expiry; unknown live
handles retain their reservations and block subsequent dispatch.

`n36-source-execution-v2` adds an interpreter-bound, process/context/phase-bound
proof for exactly `os.path -> posixpath`. The producer checks the live object
chain, canonical name/spec/frozen loader, `_imp.is_frozen`, and both exact
inventory file/hash records. The parent validates the ordinary runtime receipt,
its external binding, the execution binding, the interpreter, canonical frozen
membership and both inventory records before allowing this single exemption.
No arbitrary name, path-only or equal-hash exemption was added. Existing
compiled/startup checks and generated/native/_cyutility audit code remain.
Controller-only attestations without external bindings cannot grant the alias
exemption during parent runtime-receipt verification.

Old v1 execution receipts and old plans are not rewritten or upgraded in place.
The new CPU diagnostic aligns process start ticks with production's string
representation and checks the pinned STOP pair/deadline. Its snapshots remain
`after=False`; the fresh test receipt uses a synthetic CPU context and partial
inventory. Neither is post-episode coverage or a production source freeze.

Follow-ups remain: independent source review; complete committed scientific and
engineering source freeze and all dependent manifests; immutable isolated
runtime/controller checkout composition; complete worker receipts including
post-episode required modules; and separately authorized finite N36R2 admission,
accounting, resource routing and detached root approval. Other frozen aliases
receive no exemption here and must still satisfy existing executable coverage.
Preserve both old INVALID charges and the retained 504 dispatches /
75.49265038509455 GPUh. No scientific promotion or completion is claimed.
