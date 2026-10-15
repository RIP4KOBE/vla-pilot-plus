from pathlib import Path
import hashlib,json,subprocess
V=Path(__file__).resolve().parent;I=V/'implementation'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=I,text=True).strip()
logs=[('cpu-arithmetic-v1.log',12,'PASS','v1',0),('cpu-native-v1.log',2,'PASS','v1',0),
 ('cpu-controller-v1.log',0,'COLLECTION_ERROR_GUARD_BLOCKED','v2',2),('cpu-backend-v1.log',48,'PASS_WITH_PUBLIC_METADATA_GUARD_DENIAL','v2',1),
 ('cpu-controller-v2.log',106,'PASS','v3',0),('cpu-gates-v1.log',103,'PASS','v3',0),
 ('cpu-closure-v1.log',32,'PASS','v3',0),('cpu-worker-v1.log',16,'PASS','v3',0),
 ('cpu-arithmetic-final-v1.log',34,'PASS','v3',0),('cpu-final-scope-v1.log',24,'PASS','v3',0)]
results={'schema':'n25-conditional-controller-cpu-results-v1','commit':commit,'status':'CONDITIONAL_CPU_PREPARATION_COMPLETE_NOT_GPU_RELEASED',
 'score':'Unknown/no N25 online experiment','all_scientific_phase_a_bytes_unchanged':True,'threads':2,'interop_threads':2,
 'cuda_initialized':False,'gpu_processes_started':0,'model_calls':0,'provider_calls':0,'simulator_steps':0,
 'logs':[{'path':str(V/name),'sha256':sha(V/name),'passed':passed,'status':status,'guard':guard,'blocked':blocked}
         for name,passed,status,guard,blocked in logs],
 'counts_note':'Log pass counts overlap. Earlier failure/blocked runs are preserved and not represented as clean PASS.',
 'initial_failure':'Legacy test import attempted frozen N22 plan read; guard rejected before content read. No attempt/protected payload read. Public /proc/cpuinfo metadata also blocked, then explicitly allowed in v3.',
 'fixture_fix':'Test-only AST loads exact legacy timeout bodies with synthetic contract globals; no production classifier or globals changed.',
 'source_manifest':{'path':str(V/'source-manifest-controller-v1.json'),'sha256':sha(V/'source-manifest-controller-v1.json')},
 'guard_final':{'path':str(V/'n25_cpu_guard_v3.py'),'sha256':sha(V/'n25_cpu_guard_v3.py')},
 'remaining_prerequisites':['root terminal predecessor adoption','root exact finite budget record/adoption',
 'root committed source/runtime/reverse/old-quality proof review','one actual metered GPU7 tensor proof',
 'root post-proof local cap and Dev review/adoption/release'],
 'limitations':['CPU does not prove CUDA rounding or online efficacy','Fixed synthetic cases are not universal numerical proof; bounded first-guided native witnesses remain mandatory',
 'Later RBF calls have scalar consistency, not exact tensor replay','All-zero gradients are valid and no mechanism activity threshold exists',
 'Original N24 error/status and earlier CPU logs are immutable']}
(V/'cpu-test-results-controller-v1.json').write_text(json.dumps(results,indent=2)+'\n')
rows='\n'.join(f'| `{name}` | {passed} | {status} | {guard}; {blocked} |' for name,passed,status,guard,blocked in logs)
report=f'''# N25 conditional Phase B CPU handoff

Commit `{commit}`; branch `codex/n25-actuator-clipped-rbf`; clean source at delivery. **CPU preparation complete, no GPU/Dev/protected release. N25 score remains Unknown.** Root alone owns source integration, private state/budget/adoption and online execution.

The implementation adds independent native witness auditing, profile-bound same-process worker receipts, a one-shot tensor resource controller, and the closed40-cell C0/Q0/N23/N25 Dev controller. Scientific helper/RDT/profile remain exactly Phase A aadec3f. Of236 Phase A files,234 remain byte-identical; only the runner and worker receive explicit routes. Worker13 other functions remain exact; runner77 other functions remain exact. The reversible shared-route record restores the original two source files exactly. Final manifest binds257 files and internal digest8c9c62e223a2bf11e7a4815a0d06474d357a68fd1efa02725dbbcd78c7f50fe2.

The new independent reference uses original full dtype/layout and native byte comparison (including signed zero), separate custom derivative0 at both bounds, same operation order, same-call origins and actual before/operand/after. Fixed proof cases are6×FP32/BF16 atB16. It checks original strict-interior parity, saturation/coincidence, no extra production origin acquisition, malformed input/horizon, wrong clipped geometry and five single-element nextafter corruptions. Full guided-loop CPU tests preserve176/11 and independently verify all11 bounded native witnesses, real serialization and11 corruption classes. This is independent source arithmetic, not a different physics approximation or a CPU-as-CUDA claim.

The resource proof counts **one health-ledger process, zero episode attempts**, <=60s+40s. Existing health accounting charges its full process wall to cumulative100h and recovery GPU-hours, without consuming a recovery episode slot. Reservations/failures permanently consume that one opportunity. A cleanup fault preserves cost with incomplete-measurement flags, blocks proof and requires root reconciliation. No new provider/EGL probe, model, simulator or historical tensor corpus is used. Source/runtime/current-boot/UUID/raw-native-type/16bytes/process/ledger/report hashes and all12 fixed cases must pass before Dev.

Episode capacity is separate:40primary+max2 exact sole-Codex-timeout recoveries, no valid-failure retry, same frozen cell each time, maximum42 attempts. Missing finite root budget authority blocks admission; this source does not adopt or claim current bucket sufficiency. Later finite baseline/dev/total amendment is explicit;100h,validation180/formal40/recovery20 and protected32/12 hours stay fixed. Local cap is frozen once after actual proof accounting and <=min22/unprotected remaining. Every dispatch requires its full1840s. Budget exhaustion is incomplete/INVALID; only complete task quadruples can trigger numerical futility. Full40valid plus>=5/10 and>=all controls/substantiveQD/ED is required for promotion.

C0/Q0 provider-mode omission, original N23 quality audit and zero-guided metric-file absence are preserved. N25 requires its additional gate even when all markers are removed. The original timeout classifier body and derivative gates are unchanged; the narrow private evidence-reader wrapper binds both reader identities. Wrong/missing evidence, noneligible faults, failed recovery, missing receipt and status/journal prefix divergence retain all costs and close INVALID. No validation/formal launcher exists.

## CPU evidence

| Preserved log | Passed | Disposition | Guard; rejected reads/events |
|---|---:|---|---|
{rows}

Counts overlap across targeted regression runs. Required final checks passed under guardv3:2 CPU/inter-op threads, CUDA hidden/uninitialized,0blocked events. Existing fkd SyntaxWarning is unchanged. The v1 controller collection failure is retained: an old contract import tried to read a real **static N22 plan**, and the guard blocked it before contents were read. No attempt/protected outcome was read. Tests now compile the exact old function bodies with synthetic static globals, without changing production modules. Earlier /proc/cpuinfo dependency metadata denial is separately preserved and explicitly allowed in v3; no general read scope was widened. Root authorized one exact aggregate N24 terminal review read to match its actual schema; its result/ledger/attempt references were not followed in this CPU phase.

Reproducible targeted checks from the isolated implementation worktree (fresh basetemp name):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \\
/home/hynx/miniconda3/envs/vla-pilot/bin/python -c 'import runpy,sys;runpy.run_path(sys.argv[1]);import pytest;raise SystemExit(pytest.main(sys.argv[2:]))' \\
../n25_cpu_guard_v3.py -q -p no:cacheprovider tests/test_qd_ed_n25_native.py tests/test_qd_ed_n25_backend.py \\
--basetemp=../fixtures-root-review-new
```

Remaining controller/recovery checks are in `tests/test_qd_ed_n25_controller.py` and `tests/test_qd_ed_n25_recovery.py`; the full original validator is exercised through synthetic real-runner-shaped fixtures. No broad historical/protected test suite was invoked.

## Review and activation

`docs/03_evidence/qd_ed_final/n25/controller-contract-v1.md` defines exact schemas and root-only activation commands. Ten immutable wrappers under `phase-b-templates-v1/` all have executable=false and authorization=false; missing source/runtime/proof/adoption refs stay null. They cannot be passed directly as authorities. No actual frozen plan, readiness, preflight proof or release was created.

1. Root checks the full source manifest, the reversible route record, unchanged science and settled historical N23 quality proof. Old proof certifies quality only.
2. Root constructs the real N24 predecessor wrapper against n24-root-terminal-review-v2/source230 manifest, result/count/native/plan/ledger bindings. No fabricated accepted/source_commit fields are expected from that review.
3. Root adopts its exact finite budget record and one-resource authority under the private locks, then creates the exact arithmetic source review and release. Source is final before this sole GPU check.
4. Root integrates the same committed source, runs the one resource process and retains any failed proof/cost. No automatic second check is permitted.
5. Only after success, root freezes the local cap and final Dev source/runtime review/authority, builds the exact40-cell plan, reviews its commands and releases its one non-resumable supervisor. Validation/formal stay closed.

All source/artifacts are within the central N25 variant. Owning W, active/closed experiment evidence, state/ledger/locks/Arbor/budget and credentials were not modified. No online result or physical benefit is claimed.
'''
(V/'cpu-controller-report-v1.md').write_text(report)
files=['conditional-dev-controller-protocol-v1.md','independent-arithmetic-protocol-v1.md','cpu-controller-report-v1.md',
 'cpu-test-results-controller-v1.json','source-manifest-controller-v1.json','source-diff-controller-v1.patch',
 'source-paths-controller-v1.json','static-source-check-controller-v1.json','n25_cpu_guard_v1.py','n25_cpu_guard_v2.py','n25_cpu_guard_v3.py',
 'cpu-template-generation-v1.log','write-phase-b-templates-v1.py','build-reverse-route-record-v1.py']+[x[0] for x in logs]
files+=['phase-b-templates-v1/'+p.name for p in sorted((V/'phase-b-templates-v1').glob('*.json'))]
manifest={'schema':'n25-conditional-controller-delivery-v1','commit':commit,'executable':False,'authorization':False,
 'files':[{'path':str(V/p),'sha256':sha(V/p)} for p in files]}
p=V/'delivery-manifest-controller-v1.json';p.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({'commit':commit,'deliverables':len(files),'report_sha256':sha(V/'cpu-controller-report-v1.md'),
 'delivery_sha256':sha(p),'source_manifest_sha256':sha(V/'source-manifest-controller-v1.json')}))
