# N36 SR-01 / SR-02 CPU repair

This change repairs two findings against candidate
`e7cdf2c09a60ffb1d248f073c5639303b2ef01fa`. It is not source adoption,
runtime certification, an execution release, or a comprehensive source review.
Independent repair review is required before any adoption or prospective run.

## SR-01: executing source

The N36 runner must be started with the externally inventoried interpreter and
the absolute, frozen bootstrap path:

```text
PYTHON -I -S -B -X pycache_prefix=/dev/null ROOT/scripts/qd_ed_n36_bootstrap.py scripts.qd_ed_n36_runner [existing plan/release arguments]
```

The runner constructs the same entry for its worker. Direct runner/worker `-m`
entry and in-process execution without the bootstrap are rejected. `-B` alone is
insufficient: the non-directory `/dev/null` cache prefix prevents cache reads
even for CPython's pre-script encoding imports. The bootstrap requires isolated,
no-site, no-bytecode-write, unoptimized startup and the character-device prefix.
Before other Python dependencies load, it installs a source-only
`SourceFileLoader.get_code`, preserving the real loader class and module paths.
Sourceless and zip execution are rejected. Only explicit PYTHONPATH directories
and system site-package directories are added; `.pth`, sitecustomize and user
site startup code are not executed. No shared dependency is edited or cleaned.

Every source-loader compilation records a digest of the actual input bytes.
Worker receipts before Main and after the audits join those digests to the
external source/runtime inventories. Missing, changed, unrecorded and cached
Python modules reject. Parent verification also requires executable coverage of
the existing source/runtime module receipts. Main uses its exact absolute source
path through the same loader, retaining `run_path`'s `__spec__=None`, empty
`__package__`, temporary `__main__`, and argv semantics. Its compiled record
survives after the temporary module is removed.

Explicit exceptions retain the existing trust boundaries: built-in/frozen code
is interpreter-bound; native extensions remain externally inventoried and the
mapped Torch/CUDA/driver checks remain mandatory; generated runtime modules must
still satisfy the existing generator/template/content/live-origin rule. The
three pre-script encoding modules are source-only under the impossible cache
prefix and their source hashes remain required. Torch's existing two virtual
namespaces must be instances of the inventoried `torch._ops._Ops` and
`torch._classes._Classes` classes. No general custom-loader exception is added.

This is a source-only import repair, not a sandbox against arbitrary malicious
native code or arbitrary later Python monkeypatching. Existing reviewed dynamic
provider/controller/generated-code obligations are not discharged by a source
hash alone. Actual pinned dependency materialization, full runtime closure,
startup compatibility without `.pth` hooks, and native build/kernel attestation
remain prospective release obligations. Missing paths are an error, not grounds
to restore uncontrolled startup hooks or relax inventories.

## SR-02: exact projection origins

N36 descriptor collection now carries iteration, candidate index and occurrence
identity into the existing adapter projection. The adapter returns the actual
ordered `projection_origin` sequence and native cast, and records the native
action prefix and trajectory beside the original raw EEF value. The enclosing
event carries episode, decision, step and reset identity. No additional pose
query, projection, score, candidate or policy decision is introduced.

The independent auditor requires exactly 16 ordered events between each
canonical batch and archive update, matching the recorded sequence list and all
identities. It joins raw origin dtype/shape/bytes to both the projection event
and the cached physical boundary packet, whose preceding-observation linkage is
already audited. It separately checks native actions, casts and projection bytes
before the unchanged projection/descriptor/bounds/cell arithmetic. Missing
required raw provenance fails closed; cast-equivalent values are not accepted.
The first boundary has no preceding execution observation: its anchor is the
Main cached observation packet, not an invented prior observation. Equality of
the live controller pose and that cached observation still requires prospective
validation; a mismatch must invalidate without tolerance or changing the policy.

The hypothesis, tangent proposal, close priority, lifecycle/latch, scoring,
other15/remainder, compute budget, provider condition, task/init identities and
thresholds are unchanged. Older controls omit the new descriptor metadata and
retain their prior projection events and bytes.

## Evidence and limits

`tests/test_n36_audit_repair.py` uses the review reproduction's timestamp/size
cache construction and `1.0 -> 1.001` bf16-equivalent corruption. It covers frozen
source execution, rejection of unsafe/sourceless entry, compiled-source changes,
missing executable receipt coverage, actual runner-to-worker command/`--help`
entry with poisoned worker/proposal/auditor dependencies, and Main script
semantics. It also executes the policy's decoder method from the source loader's
compiled module code with a poisoned policy cache, without constructing a policy
or model. The startup integration uses a copied tree with only the unrelated
`core` environment initializer suppressed; its inventories are synthetic, not
prospective trust anchors. It does not run the released worker body.

CPU descriptor tests execute unchanged AST-extracted policy/adapter methods,
the real recorder, descriptor/bounds helpers and independent arithmetic auditor.
They cover fp32/bf16 and initial/first/final update identity; negatives cover raw
origin corruption (including both copies), absence/order/identity, observation,
action, cast and trajectory corruption. Baseline source parity checks retain
older-control native bytes, events and pose-query counts. No model, provider or
simulator function is called. These tests do not certify a complete live episode,
CUDA reduction equivalence, native build provenance, overhead, task outcomes or
scientific efficacy. Full frozen runtime and whole-episode release obligations
remain open. Commands, timings, failures and final file hashes are recorded in
the authorized audit-repair report directory.
