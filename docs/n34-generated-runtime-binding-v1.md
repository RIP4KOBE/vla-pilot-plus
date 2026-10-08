# N34 prospective generated runtime binding

This is an operational implementation for root review, not a production manifest,
release, dispatch authorization, or scientific result. It supports only installed
Torch's `_remote_module_non_scriptable` module. The existing closure v1 remains
available for ordinary absolute-path records; generated rules require closure v2.
No scientific, controller, native/reference audit, threshold, or dependency files
are changed.

## Reviewed generation

The reviewed `torch.distributed.nn.jit.instantiator` creates `_TEMP_DIR` using
`tempfile.TemporaryDirectory()` at interpreter import, publishes its name as
`INSTANTIATED_TEMPLATE_DIR_PATH`, registers cleanup and appends the directory to
`sys.path`. `instantiate_non_scriptable_remote_module_template()` uses the exact
name `_remote_module_non_scriptable` and the template's CUDA-capable text branch,
formats fixed strings, writes `<directory>/<name>.py`, and imports by name.
Selecting that text branch does not execute CUDA work. These tests never call the
generated forward functions, load models, or initialize an environment.

The supported source commitments are:

| Source | SHA-256 |
| --- | --- |
| `torch/distributed/nn/jit/instantiator.py` | `567d1314ee27ff0b3bd22e7c4d1157246469de25e7a3183d96debe167b193615` |
| `torch/distributed/nn/jit/templates/remote_module_template.py` | `0ff1856bbd031b5298d46c06c0502abc20bd804f42c1949ed4127e8c773660cc` |
| Prospective formatted UTF-8 source | `8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8` |

The rule pins the first two hashes in operational source as well as requiring
externally frozen records. A changed generator or template requires review and a
new rule implementation; rehashing new bytes does not authorize them.

## Prospective manifest construction

Root must construct and freeze a new external closure before production execution.
Retain the existing `runtime`, `interpreter`, `versions`, and
`distribution_versions` bindings and complete ordinary `modules` inventory. Set
`schema` to `n34-runtime-source-closure-v2`. Add this exact-shaped field:

```json
{
  "generated_modules": {
    "_remote_module_non_scriptable": {
      "rule": "torch-remote-non-scriptable-v1",
      "generator": {
        "path": "/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/torch/distributed/nn/jit/instantiator.py",
        "sha256": "567d1314ee27ff0b3bd22e7c4d1157246469de25e7a3183d96debe167b193615"
      },
      "template": {
        "path": "/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages/torch/distributed/nn/jit/templates/remote_module_template.py",
        "sha256": "0ff1856bbd031b5298d46c06c0502abc20bd804f42c1949ed4127e8c773660cc"
      },
      "sha256": "8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8"
    }
  }
}
```

The generator and template records must also appear identically under their full
Python names in ordinary `modules`. Remove the generated module's obsolete
absolute temporary path from `modules`; include its exact name in
`required_after`. The generated name cannot appear in both inventories. No other
generated names or extra rule fields are accepted. The ordinary inventory must
cover all external file-backed imports, including attestor dependencies. No
`__mp_main__` probe alias or probe directory is a production trust input.

Before imports, the verifier checks both frozen source files and their supported
hashes, parses the template's constant strings with `ast.literal_eval`, and formats
these exact parameters without executing Torch or the template:

```python
assign_module_interface_cls = 'module_interface_cls = None'
args = '*args'
kwargs = '**kwargs'
arg_types = '*args, **kwargs'
arrow_and_return_type = ''
arrow_and_future_return_type = ''
jit_script_decorator = ''
```

It concatenates `_TEMPLATE_PREFIX` with
`_REMOTE_FORWARD_TEMPLATE_ENABLE_MOVING_CPU_TENSORS_TO_CUDA`, encodes the formatted
text as UTF-8, and compares its hash to the external content commitment. Thus the
expected content is computable before any generated import; neither a receipt nor
a previously observed temporary path approves the production instance. Root must
freeze the whole closure through the existing external reference/hash mechanism
and update the operational source commitment independently. This change does not
construct or adopt that production closure.

## Live checks and lifecycle

`verify_runtime` also checks any already-loaded generator/template/generated
instance. `attest_runtime` inventories the verified generated instance alongside
ordinary modules. Before import the generated instance can be absent; after import
`after=True` requires it via `required_after`.

For all three participating modules, live checks bind `__name__`, `__file__`,
`__package__`, `__cached__`, spec name/origin/location/package/cache/loader-state,
and the exact `SourceFileLoader` type, name, path and `__loader__` identity.
Generator/template paths stay absolute and externally pinned. Generated source
must be a regular, canonical, non-symlink file with the frozen content hash,
located at precisely `<generator._TEMP_DIR.name>/_remote_module_non_scriptable.py`.
The owner must be an actual `TemporaryDirectory`, its finalizer must remain live
and refer to that owner and directory, and the exported directory path must match.
The directory must exist and be canonical and non-symlinked.

This accepts different generator-owned directories across interpreter processes;
it does not trust `/tmp`, a filename prefix, or a module name by itself. Other
loaded modules in the directory (including aliases) and other `_remote_module_`
names are rejected, even if included as ordinary records. Unexpected ordinary
file-backed modules retain the existing complete-inventory rejection. Checks for
generated modules run before the repository-source inventory exemption.

The returned inventory contains the actual live path and frozen hash for audit
reporting only. Reusing that path as an ordinary record is not the prospective
rule. Verification is a point-in-time source/origin attestation, not a sandbox or
proof against arbitrary in-process memory forgery, hostile loaders elsewhere, or
filesystem changes after verification. It preserves the existing attestation
trust model; it does not prove native/reference closure or worker readiness.

## Focused CPU validation

Run in this isolated checkout:

```sh
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -B -m pytest -q -s -p no:cacheprovider tests/test_n34_generated_runtime.py tests/test_n34_source_controller.py -k 'generated_runtime or runtime_closure_verification or full_external_module_inventory'
```

Unit cases reject tampered bytes, names, file/spec/loader metadata, ownership,
directory aliases, stale rehashed generator/template files, wrong rules,
adjacent modules and unexpected ordinary modules. Existing ordinary-inventory and
v1 runtime checks are included. Dependency files are never modified.

The installed-Torch test launches four independent processes with the specified
interpreter and empty `CUDA_VISIBLE_DEVICES`: one creates an ephemeral ordinary
**test-only** inventory, two verify that frozen fixture before imports and after
real `torch.distributed.nn.api.remote_module` imports, and one rejects altered
live spec, source bytes and same-byte wrong origin, then verifies restoration.
All four paths must differ and all four content hashes must equal the prospective
commitment. Child processes use `-B`, disable bytecode writes and have a 120-second
timeout. Their generated temporary files disappear on process exit. The fixture
inventory is neither exported to owning state nor acceptable as production
approval. These checks establish this rule's behavior only.

## Retained parent receipt (operational repair)

New workers emit `n34-worker-receipt-v2`; the parent requires that version and
rejects old flat receipts. Both `runtime_before` and `runtime_after` now use
`n34-runtime-receipt-v2`, with exactly these fields:

- `schema`: the runtime receipt version.
- `binding`: the context reference, externally frozen `runtime_closure` reference,
  worker process identity (`pid`, `proc_start_ticks`, `boot_id`), and phase name.
- `modules`: ordinary runtime records, still exact name/path/hash matches to the
  external closure. Unexpected names and extra record fields fail closed.
- `generated_modules`: only explicitly authorized generated names, each retaining
  its exact frozen rule, live path/content record, generated UTF-8 source,
  module/spec/loader origin claims for generated source and generator/template,
  and checked TemporaryDirectory owner/finalizer/directory claims.

`attest_runtime` remains the live inventory API. The worker now calls
`attest_runtime_receipt`, which first runs that complete attestation and only then
captures the retained evidence. This does not bypass generated-source checks or
exempt generated names from ordinary completeness checking: generated names must
be disjoint from ordinary names, owner/template ordinary records must be present,
and `required_after` is checked over their union. If a generated instance was
already present before Main, its full retained evidence must remain identical
after Main and auditing.

The parent still verifies the external closure, including generator/template
files, supported implementation hashes, interpreter/distribution bindings, and
prospectively reconstructed source content. It verifies the retained generated
bytes against that frozen content hash, all retained metadata against the exact
supported origin structure, and the owner directory against the retained source
path. It also retains the existing context/process/start, source, CUDA identity,
controller semantics/instance, evidence, native counts, and terminal gates.
No parent generated-path lookup is needed: UTF-8 bytes and origin claims live
inside the durable, hash-referenced worker receipt. `verify_terminal` consumes
this through the same `verify_receipt` path after worker exit. The parent’s own
loaded instance, if any, is still subject to live closure checks; its temporary
path need not equal the worker’s path.

For prospective adoption, root must independently freeze the complete ordinary
inventory and the v2 generated rule described above, update the operational source
commitment to this implementation, and use matching v2 producer/consumer code.
The closure schema remains `n34-runtime-source-closure-v2`; ordinary-only closure
v1 is still supported with v2 worker/runtime receipts. There is no migration that
turns an old generated path into authority, and no fallback to flat receipts.
The test-discovered ordinary inventory is ephemeral test data, not a production
manifest. This repair creates no production closure or release.

### What retained origin evidence proves

The frozen worker checks actual live import metadata, regular/canonical source,
actual TemporaryDirectory type, owner identity and live finalizer before emitting
these claims. The process/context/phase bindings and the existing outer receipt
hash retain that checked observation. After cleanup, the parent can independently
recheck content, supported rule, binding and internal origin consistency; it
cannot re-observe a destroyed directory or finalizer. The claims are explicitly
worker attestations, not reconstructed filesystem facts or cryptographic hardware
attestations. A party able to replace the entire receipt, its trusted hash and all
consistent origin claims can forge this history. Arbitrary in-process memory
forgery, post-check races and a malicious worker remain outside the existing source
attestation trust model. Copying an internally consistent historical claim and
also forging its enclosing process/context bindings is not independently detectable.
No claim of replay resistance against that attacker or of native/runtime readiness
is made.

### Parent integration validation

`tests/test_n34_generated_receipt.py` uses the specified interpreter with `-B`,
empty CUDA visibility and two-thread limits. A discovery child builds an ephemeral
ordinary fixture; two fresh children verify that frozen fixture and import the
installed Torch generator without invoking any generated forward function. Their
retained receipts are consumed by the actual `verify_receipt` only after process
exit and verified TemporaryDirectory removal. Both distinct origins pass.

Only dispatch/context setup is substituted in the parent fixture. Synthetic
source records, controller review documents, device identity fields and scalar
native report/compute records satisfy the surrounding receipt validators; their
validators are not removed or mocked. These are schema fixtures, not executed
controller/model/simulation evidence. Tests also corrupt controller and native
fields to ensure those gates remain active. Runtime closure verification,
controller semantics verification, native receipt validation, evidence hashing
and parent receipt consumption run normally. Tampering covers the frozen rule,
retained content/hash, module/loader/cache/origin/owner metadata, process/context/
closure/phase binding, ordinary records, missing generated records, and changed
before/after origins.
