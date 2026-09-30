# N23 external legacy-metric continuation v1

Preparation only. No changes are integrated into the owning study worktree. Its exact commit remains `51104470983cdbafd08feb87f2f39b7553779405` and all 214 plan source records remain unchanged. The separately committed external checkout imports the owning runner/contracts/worker/supervisor/core and rejects shadowed imports. It calls the original `sup.one_attempt`, `c.supervised_scope`, recovery implementation and `sup.summarize`, then uses the original hash-bound external writer's `analyze`. It never replaces function globals.

The sole metric interpretation is N7's serializer-documented omitted `qd_quality_mode=provider`, bound to the exact candidate profile and accepted raw native cost/quality/selected-action/parent evidence. Wrong explicit modes remain fatal. N23 and its auxiliary counters use the original checks unchanged. No GPU/model/provider/Stage/controller/numerical algorithm changes or additional backend preflight.

## Root review and adoption

Run the review in a fresh Python process from the owning worktree with `PYTHONPATH` pointing only to the external `continuation` directory; do not start from the external checkout with its scientific packages pre-imported. Imports are checked before and after loading the frozen modules. Root performs the existing 214-source/runtime/input checks and the actual three-prefix checks; executor tests consult synthetic evidence only.

```python
import n23_continuation_contract as x
owned = x.load_owned()
plan, manifest, runtime = owned.r.validate_plan(x.PLAN, root=owned.root)
failure = x.immutable_inputs(owned)
source = x.source_record()
owning = x.owning_source(plan, owned)
events = owned.r.read_events(owned.root/'data/attempt-ledger.jsonl')
prefix = x.prefix_gate(plan, failure, events, owned, x.acceptor(plan, manifest, owned), initial=True)
review = x.review_payload(plan, source, owning, owned)
```

`review_payload` is the exact closed schema `n23-continuation-source-review-v1`, not an adoption. It binds exception/failure/original plan/runtime/backend proof, original full source, external full source and original imported writer, exact three attempt IDs, untouched 37 keys, unchanged limits, and protected phases false. Root, after its independent review, writes it immutably to `continuation-source-review-v1.json`. No self-referential report hash is compiled into the source manifest.

Root constructs the exact authority with `x.authority_payload(x.ref(x.REVIEW), plan, owned)` and writes `continuation-adoption-v1/authority.json`. Under the existing private runner/state locks, it rechecks the same prefix, no owned worker, full remaining original capacity and all protected reserves, and adopts only `research-state.yaml[n23_legacy_metric_continuation_authority] = x.ref(x.AUTHORITY)`. This state change does not amend budgets or original release. The authority expressly permits one initial launch, no new backend test, validation or formal execution; it cites continuing autonomous instruction as prospective coordinator engineering authority, not a new user approval.

The executable rechecks these gates and creates immutable `execution/continuation-launch-seal-v1.json` with PID/start-ticks/boot identity before work. Existing seal or new status blocks any restart. It holds a separate continuation coordinator lock for the full run, and uses original runner/state locks for every admission. Original worker timeout and exclusive-GPU metering remain unchanged. A failure closes this one launch; further engineering continuation needs a new prospectively reviewed authority.

## Root execution, only after adoption

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python /ABS/N23/continuation_implementation/continuation/n23_continuation_supervise.py
```

No CLI overrides broaden plan, device, status, authority, prefix or source. The status is always `N23/execution/supervisor-status-continuation-v1.json`. Three original primary failures are reconstructed once, all costs preserved, then only original rows 3..39 may dispatch. The original 42-attempt/2-recovery/22-hour caps include the previous three attempts. Typed recovery is delegated unchanged; valid task failures are never retried. Each recovery is still checked before its dispatch and included in costs; failed recovery is fatal.

After terminal closure, run the sibling `n23_continuation_report.py` under the same environment. It acquires the coordinator/runner/state locks, verifies no worker, original prefix, new authority/source/seal, and uses the original terminal analyzer with the corrected acceptor. It writes immutable `result-continuation-v1.json` (`n23-dev-continuation-result-v1`) and `dev-terminal-ledger-snapshot-continuation-v1.jsonl`. These include all old/new/invalid/recovery costs and explicit links to the original failed v2 record. The original result/status/ledger snapshot are never overwritten. An invalid continuation cannot promote. The existing conditional validation preparation remains inactive and requires a separate reviewed evidence-reference adapter if the full continuation promotes.

## Focused CPU verification

From the external checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p no:cacheprovider -p n23_continuation_cpu_pathguard_v1 -q tests/test_n23_n7_metrics_adapter.py tests/test_n23_continuation.py --basetemp=../n23-v2-guarded-fixtures-continuation-final
```

The guard blocks historical/protected artifacts and isolated-worktree data copies; static frozen metadata and bounded synthetic fixtures are allowed. Actual serializer and original `accepted_cell`/`verify_receipt`/`terminal_binding` are exercised with synthetic files. Only worker source-context construction is mocked in those receipt fixtures; source immutability and import-origin gates are tested separately. Dispatcher tests invoke the real original one-attempt/scoped routing with a mocked runner launch, never CUDA or API. The real frozen aggregate analyzer validates the resulting 40/41-attempt denominators, costs, futility and failure dispositions. No synthetic test establishes robot performance.
