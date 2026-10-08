# N34 production integration candidate — no release

This CPU integration is based on accepted source
`71ffff1a0f70d9874b309db9ef1843c02bf17ebf`. The proposal, native representation,
reference audit and generic audit are unchanged. N32/N32R3 are unchanged. Only
N34 has new bridge, worker, controller, source, preparation, release-validation,
runner, reconciliation and reporting modules. Existing process ownership,
exclusive-device wait, cleanup and command/config helpers are reused by import.
No N34 launch is labelled N32. Public runner/worker dispatch remains closed by
`qd_ed_n34_release.validate_release` / `qd_ed_n34_contract.require_release`.
Root must finish current accounting, deployed closure, prospective freeze and
review before deliberately wiring the release boundary. A candidate or fixture
cannot open it by setting `approved=true`.

## Prospective composition and source identities

The bridge copies the original C0/Q0 profiles unchanged, including Q0 static
launch and mechanism-pretest overrides. N34 adds observed-jaw mode only, makes
N31/N32 modes explicitly off, and binds task ID, the scientific commit and fresh
attempt ID. `expected_runtime` is constructed before any attempt from the fully
resolved policy constructor config (including Main's pretest/reward overrides)
and the exact relative-path list in `core.qd_observed_jaw_approach.SOURCE_FILES`.
It never reads a candidate trace or runtime receipt to create trust.

Operational source records bind the actual integration commit. Scientific
records bind accepted source `71ffff...`, including the unmodified core,
configs, utils, native/reference auditors and pinned RDT files. Every scientific
entry must match the operational entry. Git source verification accepts only
regular committed files, rejects symlink ancestors, and resolves all RDT
Python/JSON/YAML files through the superproject gitlink and registered local
object database. It never consults an unrelated RDT HEAD or fetches. Missing
materialized files are blockers; an empty glob cannot omit them. In particular,
`scripts.maniskill_model`, model modules imported as `models.*`, decoder,
policy, LIBERO adapter and controller dependencies must be present and bound.

The root must provide a hash-referenced `n34-runtime-source-closure-v1` with:
`runtime` reference; `modules` mapping actual Python module names to absolute
resolved `{path, sha256}` source/extension-module records; `required_after`
module list; `versions` for Python, Torch, LIBERO, robosuite and MuJoCo;
`interpreter` containing resolved executable path, SHA-256 and `sys.version`;
`distribution_versions` checked against installed metadata (at least torch,
numpy, robosuite, mujoco and transformers). LIBERO may be a source checkout; its
reviewed version must identify the source revision bound by the module hashes.
All loaded file-backed external modules are checked before/after Main, including
unanticipated imports; the closure is not inferred or expanded from a candidate
receipt. Known virtual `torch.ops`/`torch.classes` have no backing files; their
actual implementation modules remain checked. Repository modules are separately
bound to the operational source, and the executing `python -m` worker is bound
by its actual `__main__` module/spec/origin before and after runpy. This is source
and origin attestation, not an arbitrary-bytecode integrity claim.

## Exact deployed controller requirements

`qd_ed_n34_controller.verify_semantics` accepts only a root-reviewed, runtime-
bound `n34-deployed-controller-semantics-v1` document. It names the actual
`robosuite.*.OperationalSpaceController` module, class and source hash, plus the
expected instance fields listed in `FIELDS`. Required behavior is:

- OSC_POSE with six normalized pose channels, `control_delta=true`,
  `control_ori=true`, fixed impedance, policy frequency 20 Hz, no position or
  orientation interpolator under this initial integration contract.
- Input bounds exactly [-1,+1] in all six channels; finite positive symmetric
  output bounds, preserving zero as zero delta. Freeze exact output scales and
  `uncouple_pos_ori`, not merely a controller label.
- Translation interpreted as scaled world-frame displacement increments;
  rotation interpreted as scaled axis-angle increments. Zero rotation means
  zero increment, not an absolute orientation target or guaranteed pose lock.
- The deployed wrapper/adapter forwards the six decoded float32 channels;
  gripper -1 means opening, +1 closing. Freeze and review the actual forwarding
  and gripper implementation, not comments or a fixture controller.
- The algorithm's .01 projection convention is not a certified physical gain.
  `physical_gain_certified` must remain false. Physical response/capture and
  latency stay Unknown until separately authorized native work.

The proof includes independent `review_evidence` references for `set_goal`,
`scale_action`, and `wrapper_and_gripper`, each explicitly a deployed source
review bound to the same runtime and marked `fixture_only=false`. Those documents
must contain root's actual source/version/config findings. This executor does
not create them. A metered worker temporarily wraps only the reviewed class's
constructor, records and validates the resulting actual instance fields, then
restores the constructor. It changes no actions, settings or control law. An
unseen controller, alternate class/source, non-delta mode, changed scales or
missing instance stops acceptance. All instances must match; observations are
not used to promote the external proof. Unsupported installed attribute names
or semantics require root review and a new verified adapter, never a bypass.

## Worker, controller and release behavior

Main and both CPU audits execute in the same metered worker. The unchanged
generic audit must accept complete evidence first, followed by mandatory
`n34_observed_jaw_audit`. Controls run their unchanged native checks and must
have no N34 markers, metrics, gate or runtime binding. The parent reads bound
receipts and scalar/compute metadata; it does not replay tensors or use CUDA.
Receipts bind process boot/start/PID, command/context, runtime manifest, both
source identities, external expected manifest, source inventory and controller
instance attestation. Generic result/video/provider/cost gates still apply.

The new runner holds normal runner/state locks and launches one primary worker.
It rejects reordered/duplicate/wrong-profile/runtime/source/config identities,
retains invalid attempt wall charges, stops on invalid/unsettled evidence, and
never retries automatically. STOP prevents new work without signalling a running
worker. Timeout cleanup may signal only the parent's exact unreaped Popen child.
Admission includes 1800 episode seconds plus 40 cleanup seconds, deadline,
private device exclusivity, historical attempts/health charges, reservations,
weekly/current private balances and protected validation/formal reserves.
`admission` retains the predecessor journal arithmetic as candidate plumbing;
its owning-authority/state bindings and explicit root-supplied caps require
root's current accounting review before release. No predecessor balance or
private spending cap is silently carried forward; validation/formal reserves
remain protected. No current balance is claimed here.

## Disabled fresh Dev candidates

The task definition is `n31_dev_task_identities.json`, with fresh
`n34_dev_tNN_{c0,q0,n34}_20261008` attempt IDs and task-major C0/Q0/N34 order.
Thirty primary cells is a ceiling, not a spending promise. Limits remain zero
automatic recoveries, 5 GPU hours including attributed preparation/audit/cleanup,
1800 seconds per episode plus 40 cleanup. No carried control outcomes.
Every prospective outcome is Unknown. The original necessary Dev gate remains
all 30 valid fresh cells, N34 >=5/10 and >=both matched controls. Futility is
checked only after complete valid triples when candidate successes plus unrun
tasks is below five. Activity/proposal/selection counts are not success gates.
Validation/formal remain closed; passing Dev is not automatic promotion.

The output directory contains plan/protocol CANDIDATES, not accepted production
artifacts. Root must recheck fresh-ID absence in the complete owning journal,
finish settlement/accounting/protected reserves under current authority,
materialize and verify pinned RDT and deployed runtime/controller closure,
freeze actual operational source and all 30 external expected manifests, review
exact official current-login gpt-6-astra runtime/provider conditions, and issue
its detached prospective review/release after wiring the closed boundary.
No CPU fixture certifies those steps or actual installed-environment semantics.
