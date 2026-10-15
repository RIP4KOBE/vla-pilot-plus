**Independent engineering review — full consumer gate FAIL**

Source: `e4914cb4baf91bbb66f91e25584652eb273b8904`; base: `30c6321715df86c5bab623db607bab2811aed56d`. Review only; no release, scientific score, adoption or promotion.

The fixed generated Torch import repair passes bounded review. The complete retained CPU receipt still fails verification because two existing CPython importlib aliases are represented inconsistently by producer and consumer. The green generated-import test is not full acceptance.

| Finding | Result | Code |
| --- | --- | --- |
| F1 Exact source and evidence identity | PASS | `scripts/qd_ed_n34_source.py`; `scripts/qd_ed_n36_bootstrap.py`; `scripts/qd_ed_n36_generated.py` |
| F2 Fixed generated Torch provenance | PASS | `scripts/qd_ed_n36_generated.py:13-39`; `scripts/qd_ed_n34_source.py:155-217`; `scripts/qd_ed_n36_bootstrap.py:28-40,92-114` |
| F3 PathFinder native and namespace coverage within declared boundary | PASS | `scripts/qd_ed_n36_bootstrap.py:117-132`; `scripts/qd_ed_n36_source.py:30-45` |
| F4 Tamper rejection and generated producer-consumer join | PASS | `scripts/qd_ed_n36_source.py:149-161,219-237,244-257`; `scripts/qd_ed_n34_source.py:513-572`; `scripts/qd_ed_n36_worker.py:355-374` |
| F5 Full consumer rejects legitimate frozen importlib aliases | FAIL | `scripts/qd_ed_n36_source.py:187-195`; `scripts/qd_ed_n36_source.py:240-257`; `scripts/qd_ed_n34_source.py:443-454` |
| F6 Green generated-import test is not a full consumer acceptance gate | FAIL | `scripts/test_n36_generated_import.py:118-150`; `scripts/test_n36_generated_import.py:163` |
| F7 No production audit weakening found in scoped diff | PASS | `scripts/qd_ed_n34_source.py:155,218-225,418,430`; `scripts/qd_ed_n36_generated.py:31`; `scripts/qd_ed_n36_source.py:151-153` |

**Precise full-consumer cause and narrow repair**

CPython exposes each frozen object under a public importlib alias, sets __name__ to that alias and __file__ to its .py counterpart, but retains canonical frozen __spec__.name. Producer stores spec.name (_frozen_importlib / _frozen_importlib_external); runtime inventory uses sys.modules keys including importlib._bootstrap / importlib._bootstrap_external. Consumer filters ordinary rows by membership of the inventory key in frozen_modules, so both aliases remain and are incorrectly required to have compiled .py receipts. They executed interpreter-frozen code, not those .py files.

Fresh replay reproduces `N36 module missing executable receipt: /home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/importlib/_bootstrap.py`. Exactly two ordinary Python inventory rows lack execution coverage:

- `importlib._bootstrap` → `_frozen_importlib`
- `importlib._bootstrap_external` → `_frozen_importlib_external`

The installed CPython aliases share their canonical module objects and FrozenImporter loaders. Their canonical names satisfy `_imp.is_frozen`; public aliases do not. Both canonical names are already in the retained frozen list, and each alias/canonical pair has equal retained path/hash records. The installed `importlib/__init__.py:15-48` creates these aliases and assigns the public `__name__` and source-looking `__file__`.

Add an explicit closed two-pair frozen-importlib alias proof, alongside the existing os.path proof. Bind interpreter identity, external context/runtime-closure/process/phase; validate alias is canonical object and importlib attribute, exact spec canonical name/origin/frozen loader, _imp.is_frozen(canonical), module __name__ equal to the public importlib alias (not canonical), package importlib, canonical lexical __file__, and identical frozen inventory path/hash records for both keys. Retain and verify the proof before excluding only these aliases from ordinary executable coverage. Require matching canonical entries in frozen_modules. Do not add aliases to frozen_modules directly, skip all importlib paths, synthesize compiled receipts, or infer identity from equal hashes alone.

Removing only the two alias rows from an in-memory diagnostic copy makes replay pass. This localizes the failure; it does not establish alias identity in the historical worker and is not an acceptable production repair. No source or receipt file was modified.

**Generated provenance, PathFinder and audit strength**

Admits the fixed _remote_module_non_scriptable filename and SHA256 8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8, pinned generator/template files and executed source digests. N34 derives bytes from pinned template literals, checks canonical source/spec/SourceFileLoader fields and live TemporaryDirectory ownership/finalizer. Admission requires the owned directory contain exactly the generated file. The actual bytes passed to source_to_code are hashed before compilation.

Guard precedes PathFinder, validates sys.path, every returned spec origin, and each namespace/package search location. Focused exact-AST control-flow probes reject foreign native, foreign namespace and mixed namespace specs; allow in-root/in-prefix controls. Retained real test rejects extra .py and .so entries in the generated directory.

The retained .so probe is invalid native content rejected by the directory check; it does not establish successful native-loader execution coverage. New namespace/native probes supply synthetic PathFinder results, with validate_search stubbed. Earlier/custom meta-path finders or direct loader calls are outside this PathFinder guard; source/runtime/native attestations remain necessary.

Generated compiled origin is joined to live inventory and retained generated record, with externally supplied process/context/phase binding. Retained temporary directory is gone and focused consumer still passes without reopening it. Eight fresh negative checks reject missing receipt, foreign search path, content, owner, process binding, compiled origin, omitted generator execution and omitted template execution.

Retained claims rely on the bound trusted worker; no fresh production closure or formal process proof was manufactured. Source verification uses after=False, while the unchanged full worker separately requires after=True completeness and before/after identity stability.

scan_loaded=False is used only by the new per-import admission helper. Default remains True; runtime closure verification, runtime attestation and N36 execution attestation still scan loaded modules. Parent consumer still fails closed. New search path authority comes only from validated bound generated evidence. No arbitrary /tmp allowance, discovered-hash trust, bytecode allowance, or production alias skip was introduced.

The general checkout/interpreter origin branch remains trusted; the special exception is exact for external generated directories. This does not claim comprehensive protection against custom finders, direct loaders or arbitrary mutation of Python internals. Full attestations remain required.

**Test-level audit weakening**

The test catches any ValueError from the full consumer, saves its text and then reduces ordinary modules to generator, template, os.path and posixpath. It neither asserts the known error exactly nor requires full_consumer_error to be absent. An unrelated new full-consumer failure could still leave the test green.

Keep focused generated provenance coverage clearly named. Until alias repair, constrain an expected failure to the exact known cause rather than swallowing arbitrary ValueError. After repair add an unsuppressed round-trip assertion on the complete receipt plus negative tests for both alias proofs; retain full ordinary inventory.

The failure mechanism predates this diff. The new test transparently retains the full error, but catches any ValueError and checks a reduced inventory. Production verification still rejects the complete receipt; no broad alias exception was added.

**Evidence and validation**

- Reused retained real-bootstrap test: 11 live rejection cases and six retained-receipt rejection cases, with temporary directory cleanup. `tests-7`: one focused test passed in 6.69 seconds while reporting the full-consumer error.
- `tests-3` recorded 53 existing tests passing within a failing intermediate run; these are retained evidence, not a new exact-final-source full-suite certification.
- Fresh unchanged full retained replay: expected failure reproduced. Focused retained replay: PASS after the temporary path was removed.
- Fresh eight retained mutations: all rejected (missing receipt, foreign search path, content, owner, binding, compiled origin, absent generator execution, absent template execution).
- Five focused PathFinder control-flow probes: expected results for foreign native, foreign namespace, mixed namespace and two trusted-root controls. These use synthetic specs, not actual native loading.
- Two fresh read-only CPU test commands, each bounded by 25 seconds, used 5.333 seconds measured wall time (6 seconds conservative accounting), below the 120-second budget. Two-thread environment; no fresh pytest or Torch bootstrap run.
- Full scripts, exact interpreter/environment, outputs, exit codes and timing are embedded in `report-v1.json → tests.focused_runs`. No test artifact files were created.

**Source and report hashes**

All five working files match the exact source commit. Full-index diff matches the retained patch byte for byte: `0db6142f309261ed60e6936f9de53cb2bd00aca67d1a843c761976a94f0f72c5` (21578 bytes). Git tree: `ec45d295ed809a3d85804402c68b9c3b26a157e1`. Tracked worktree remains clean.

| Changed file | SHA256 at reviewed source |
| --- | --- |
| `scripts/qd_ed_n34_source.py` | `be71a7cc706915c7466b641a68d6ece2689857668baf74fa2a58aa8181ca70b4` |
| `scripts/qd_ed_n36_bootstrap.py` | `b58430c8d7381e13791ad62cc00ce8cb11d7c344192df9729f0d4bdbc306fb64` |
| `scripts/qd_ed_n36_generated.py` | `e1f43e04e4afabba62b81468d8bf68da6cd66d99f3bc074a703ef7bc83d5e523` |
| `scripts/qd_ed_n36_source.py` | `939ff8ab3b41cb8cbe1b116ff94cc9ba0ac6ada02dccc755b700127ce0a97492` |
| `scripts/test_n36_generated_import.py` | `80a0ea69887d0e7c997416c2fb700a1745e0d7f9a1a95b9a45979c818cde85c7` |

| Evidence | Verified SHA256 |
| --- | --- |
| authority | `f350688b56ef5169bcb470358812f71e205603170a6c2a59a9e24b90fc669cad` |
| prior_report | `3057f39f5c9530657603f9f8240694978ddd3474958b3aec938a55856f9d6fd6` |
| terminal_reconciliation | `ea7c7e1b5b88a52674d5218335334881431ac79085e4d41cb8f22fc0cf9d06e4` |
| retained_cpu_receipts | `b907c9fa8583703f5ef98d01281ad3392c567676f7148cef4575833a084347cc` |
| test_commands | `e6d8e9d25d2a994be1cdc1b9b97595fdec81ba6dfb1a39eef5c855953348d619` |
| source_delta | `0db6142f309261ed60e6936f9de53cb2bd00aca67d1a843c761976a94f0f72c5` |
| source_delta_hashes | `65bd5cf02eca16a8bb91ab7345eccdd507d56eeeb2959c58850287159626bfc2` |
| tests_3_log | `3945a4c4c845628c6430580e355181af48bfec039d8543bcafc5b094fdfa3040` |
| tests_7_log | `ec0a591397edf18e1d64e26326f8ed45b31f327394823ae8a5d5df91178bd5b8` |
| This report JSON | `bdd601280b65b0ad8ff4ac7dce18d8b138e7393d30a228132df20b1133e1d232` |

Full paths, byte counts, before/after source hashes and direct-consumer hashes are in the JSON report. Default abbreviated-index git diff differs in presentation only; the full-index diff is an exact retained-patch match.

**Remaining gates**

- Implement and independently review the closed two-pair importlib alias proof in separately authorized work; no source change was made here.
- Run unsuppressed full retained/full CPU producer-consumer round trips, including both canonical aliases, and negative tests for object/loader/spec/name/path/hash/interpreter/process/context/phase substitution and missing canonical evidence.
- Retain complete ordinary inventory and enforce full worker before/after coverage; generated-only passing tests do not satisfy worker acceptance.
- Fresh recovery/source/runtime inventories, frozen plan, root release and any adoption are separate authorized coordinator work. No such artifacts were generated or validated here.
- No scientific score, promotion or dispatch; existing ledger totals remain 505 attempts and 75.52725286641478 GPUh.

Only these two reports were written. No source edits, commits, installs, network, GPU/simulator/Main/Stage/provider calls, protected validation, broad rebuilding, prohibited document/credential/Poe reads, owner-state/ledger changes, coordinator locks/launches or child agents. Superpowers remained disabled. The supplied ledger totals remain 505 attempts and 75.52725286641478 GPUh; ledgers were not inspected or changed.

Elapsed wall time from authority creation to report write: 272.634 seconds, below 900 seconds. Authority deadline: 2026-10-11T11:13:13Z.
