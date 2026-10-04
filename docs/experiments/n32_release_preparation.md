# N32 CPU release preparation (disabled draft)

This is engineering preparation. There is no GPU release, Dev outcome, score,
protected-phase authority, source adoption or budget amendment. The scientific
runtime, independent auditor and every existing tracked file remain unchanged.

The added bridge uses the existing `qd_ed_final_runner.build_command`, frozen
C0/Q0 profiles, Hydra task composition and N32's single declared profile delta.
It compiles the exact policy dataclass, constructor and scalar parsers from
committed source without importing a model or environment. It mirrors Main's
EDS evaluation/pretest merge. The constructor is a serialization tool; it does
not replace the full policy validator. CPU tests compare its result with the
full policy resolver for C0/Q0/N32. Steps720, frequency20Hz and chunk8 are checked.

`qd_ed_n32_prepare.prepare` requires committed source and writes thirty external
manifests **before** any worker. Inputs are source, declared row, runtime metadata
and the exact prospective command; candidate evidence is never read. Each
manifest binds all task seeds/init hashes/BDDL identity, source inventory, runtime
reference, full argument list, output identity, composed-config hash and resolved
policy config. Runtime metadata must agree on task/init and init-file/BDDL hashes.
No init tensor or historical evidence is loaded by preparation.

There are two explicit hash conventions. General documents use canonical compact
JSON (`sort_keys=True`, separators comma/colon, `allow_nan=False`). The policy
config hash uses the accepted adapter's `json.dumps(..., sort_keys=True,
allow_nan=False)` **with default spaces**. Tuple/list conversion has the same JSON
representation. Source excludes generated plans/manifests/receipts. Manifests do
not contain their own hashes or plan hashes. The plan binds each manifest's exact
file SHA256; the worker context binds plan and manifest references; audit receipts
bind context/plan/manifest/source/row/process plus report/evidence hashes. This
acyclic construction avoids self-reference.

Source inventory extends the frozen N31/shared inventory with N32 scripts,
runtime, tests and this document, and all core/utils Python and Hydra YAML files.
Preparation rejects uncommitted bytes. Worker revalidation rejects checkout,
manifest, command, runtime and task/config drift before and after execution.
Loaded repository module origins/backing bytes are attested against that source
inventory. This does **not** establish arbitrary live-bytecode integrity or
checkpoint/dependency attestation; root must retain the generic runtime inventory
and real launcher/process attestation. Synthetic tests intentionally replace Git
verification for the synthetic runtime, separately testing committed-byte
rejection in a temporary Git repository.

The worker implementation executes Main and generic/native audits in one PID.
N32 receives the independent N32 auditor with the externally built trust anchor;
controls retain the unchanged N31 native audit. The episode's 1800s timeout must
include both audits; cleanup is separately bounded at40s. Errors yield INVALID
receipts, never task failures or abstentions. Missing receipts are INVALID.
Parent verification uses an externally observed process identity, exact receipt
hashes, source/manifest/config bindings, native scalar gates and the unchanged
generic result, video, Stage and complete-cost validator. It does not replay
native tensors. The tests exercise real synthetic recorder/generic/native audit
and receipt consumption; the generic terminal validator's delegation is tested
with a spy, not a real video/provider output.

Pure supervisor functions reconcile only a unique task-major prefix. A live or
unsettled handle blocks new work; duplicate, retry, invalid and altered evidence
cannot be selected as an alternative result. Futility occurs only after a valid
complete triple when N32 successes plus remaining tasks is below5. Full Dev
completion with N32 >=5 and >=both contemporaneous controls is only a necessary
condition for root consideration. Unrun cells are Unknown. Reports retain input
charges/health events and Unknown HTTP counters. Validation20 >=10, formal10 >=5,
control comparisons and matched ablations remain closed.

`next_dispatch` composes reconciliation with a read-only guard for the exact
session `autonomy_20261004/STOP`, private allowance, global/protected reserves,
cohort cap, GPU7 UUID/idle admission and the earlier of the authority window and
2026-10-10T17:42:00Z. It requires1840s before every new primary. STOP/deadline do
not signal a running process. The caller must supply an authoritative settled
snapshot including all previous episode/health charges and reservations.

## Remaining integration and release prerequisites

This delivery is deliberately **partial release preparation**: public worker and
supervisor launch functions fail closed unconditionally. There is no executable
release/freeze operation. The prospective audit implementation is internal and
its CPU tests invoke it using synthetic evidence. Production dispatch is not
wired into the owning runner/state/ledger. No locks, ledger, driver/coordinator,
GPU health checks, provider calls, simulator or real model were invoked here.

Root must review this source, freeze the fresh task-major protocol and exact
ledger arithmetic, adopt the source/runtime/manifest inventory and supply real
review/authority/release artifacts. A subsequent reviewed adapter must connect
`next_dispatch`, same-process worker and `verify_terminal` to the existing generic
runner with its normal runner/state locks, actual process/CUDA/runtime inventory
proofs, durable reservations/charges, bounded timeout/cleanup and zero recovery.
It must verify real task-cache/init-row/checkpoint identity and loaded runtime
at launch. Draft plan review/protocol/authority/release are all null; all phase
authorizations are false. No placeholder approval hash is accepted. Root cannot
turn this draft into a release merely by flipping a boolean.

CUDA transfer/device behavior, physical capture, outcome quality, model/provider
execution, audit runtime on full720-step episodes and worst-case resource use
remain unmeasured. Source-backed AST constructor parity is CPU tested, not a
claim about arbitrary modified live bytecode. Internal HTTP counters stay Unknown.
