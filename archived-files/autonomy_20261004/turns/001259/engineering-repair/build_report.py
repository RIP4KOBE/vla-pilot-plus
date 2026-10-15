import datetime as dt
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

root=Path.cwd()
evidence=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001259/engineering-repair')
owner=evidence.parents[3]/'study_worktree'
base='88b3c28cb49f610be382b24cce4c5df57bc41661'
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
head=git('rev-parse','HEAD')
assert head=='b1d20fc0481721da6ebaab161c5a2ef7c3d50173'
assert git('status','--porcelain')==''
sys.path.insert(0,str(root))
from scripts import qd_ed_n36_stop as stop
stop.check()
owner_commit=subprocess.check_output(['git','-C',str(owner),'rev-parse','HEAD'],text=True).strip()
assert owner_commit=='ca4e6a96d049c7ebb1f302d755883388ddbfdbd8'
changed=git('diff','--name-only',base,head).splitlines()
assert all(p.startswith(('scripts/qd_ed_n36_','tests/test_n36','docs/')) for p in changed)
diff=subprocess.check_output(['git','diff','--binary',base,head])
assert diff==(evidence/'source-changes-v1.patch').read_bytes()
files=[]
for path in changed:
    old=subprocess.run(['git','show',base+':'+path],capture_output=True)
    new=subprocess.check_output(['git','show',head+':'+path])
    assert new==(root/path).read_bytes()
    files.append({'path':path,'before_sha256':hashlib.sha256(old.stdout).hexdigest() if old.returncode==0 else None,
                  'after_sha256':hashlib.sha256(new).hexdigest(),'bytes':len(new)})
selections=[
 ['tests/test_n36_stop_guard.py','tests/test_n36_frozen_alias.py','tests/test_n36_runner.py','tests/test_n36r2_draft.py'],
 ['tests/test_n36_stop_guard.py','tests/test_n36_frozen_alias.py','tests/test_n36_runner.py','tests/test_n36r2_draft.py'],
 ['tests/test_n36_frozen_alias.py','tests/test_n36_cyutility_alias.py','tests/test_n36_audit_repair.py::test_compiled_bytes_join_rejects_changed_source_and_loader','tests/test_n36_audit_repair.py::test_stale_cache_repro_and_frozen_source_execution','tests/test_n36_audit_repair.py::test_main_source_entry_preserves_script_semantics','-k','not real_import_orders'],
 ['tests/test_n36_cyutility_alias.py','tests/test_n36_stop_guard.py::test_stop_after_worker_entry_prevents_main_and_retains_receipt','-k','not real_import_orders'],
 ['tests/test_n36_stop_guard.py::test_exact_authority_accepts_supported_session_layout','tests/test_n36_stop_guard.py::test_deadline_does_not_shrink_full_attempt_requirement','tests/test_n36_release.py'],
 ['tests/test_n36_release.py','tests/test_n36_stop_guard.py::test_independent_stop_launch_races','tests/test_n36_stop_guard.py::test_worker_context_checks_entry_but_allows_settlement','tests/test_n36_stop_guard.py::test_stop_after_worker_entry_prevents_main_and_retains_receipt'],
 ['tests/test_n36_frozen_alias.py'],
 ['tests/test_n36_frozen_alias.py','-k','parent_rejects or fresh_source'],
]
results=[(1,'18 failed, 99 passed',6.08),(0,'124 passed',5.88),(1,'25 failed, 52 passed, 6 deselected',5.60),
         (0,'40 passed, 6 deselected',4.30),(1,'1 failed, 14 passed',4.57),(0,'21 passed',4.70),
         (0,'38 passed',3.39),(0,'23 passed, 18 deselected',2.59)]
tests=[]
for i,(selection,(exit_code,result,seconds)) in enumerate(zip(selections,results),1):
    tmp=evidence/'tmp' if i<=3 else evidence.resolve()/'tmp'
    env={'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2','MKL_NUM_THREADS':'2',
         'NUMEXPR_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(root)+':'+str(root/'tests'),'TMPDIR':str(tmp)}
    argv=['taskset','-c','0,1','timeout','180' if i<=3 else '120','/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B','-m','pytest','-c','/dev/null','-p','no:cacheprovider',*selection,'--basetemp='+str(evidence/f'test-run-{i}'),'-q']
    log=evidence/f'tests-{i}.log'
    assert result in log.read_text()
    tests.append({'id':i,'cwd':str(root),'environment':env,'argv':argv,
                  'shell_command':' '.join(k+'='+shlex.quote(v) for k,v in env.items())+' '+shlex.join(argv)+' > '+shlex.quote(str(log))+' 2>&1',
                  'exit_code':exit_code,'result':result,'pytest_reported_seconds':seconds,
                  'log':{'path':str(log),'sha256':sha(log)}})
receipts=sorted({p.resolve() for p in (evidence/'test-run-8').glob('test_fresh_source*/live-receipt.json')})
assert len(receipts)==1
fresh=json.loads(receipts[0].read_text())
compiled=[r for r in fresh['execution']['compiled'] if r['module']=='scripts.qd_ed_n36_source']
assert len(compiled)==1 and compiled[0]['sha256']==sha(root/'scripts/qd_ed_n36_source.py')
receipt_copy=evidence/'fresh-cpu-alias-receipt-v1.json'
with receipt_copy.open('x') as f:f.write(receipts[0].read_text())
review=evidence.parents[1]/'001256/focused-review/report-v1.json'
# Canonical sibling review path; no recursive provenance reconstruction.
review=evidence.parent.parent/'001256/focused-review/report-v1.json'
now=dt.datetime.now(dt.timezone.utc)
report={
 'schema':'node-15.6-n36r2-engineering-repair-v1','node_id':'15.6','turn':'001259',
 'status':'IMPLEMENTED_FOCUSED_CPU_CHECKS_PASS__PRODUCTION_BLOCKED','score':None,
 'started_at':'2026-10-10T02:47:22Z','completed_at':now.isoformat(),
 'elapsed_wall_seconds':(now-dt.datetime(2026,10,10,2,47,22,tzinfo=dt.timezone.utc)).total_seconds(),
 'role':'isolated CPU engineering executor; not coordinator',
 'source':{'worktree':str(root),'base_commit':base,'commits':[head],'owner_commit':owner_commit,
           'clean':True,'preserved':True,'diff':{'path':str(evidence/'source-changes-v1.patch'),'sha256':sha(evidence/'source-changes-v1.patch')},'changed_files':files},
 'review':{'path':str(review),'sha256':sha(review),'blockers_addressed':['B1','B3']},
 'stop_guard':{'authority':stop.binding(),'both_absent_at_finish':True,'deadline_checked':True,
    'binding_basis':'Exact paths and owner source pinned by explicit user repair contract; source review/freeze and detached authority remain required. Veto only.',
    'boundaries':['draft/release structural binding','admission','healthcheck reservation','healthcheck pre-start and immediate pre-Popen','post-reservation','immediate pre-worker-Popen','worker context admission','worker pre-Main','next dispatch via admission'],
    'failure_semantics':'lstat: reject entries including dangling symlinks and all access/stat errors except ENOENT; no resolution of STOP entry',
    'headroom_seconds':{'episode':1840,'healthcheck':'1840 + complete timeout/cleanup reservation'},
    'drain':'No STOP signalling. Worker settlement/context validation defaults to no admission veto. Existing timeout cleanup remains unchanged. Unsettled reservations retained.',
    'limits':'Filesystem check and process launch are not atomic; child recheck before Main closes the tested handoff boundary.'},
 'alias_proof':{'schema':'n36-source-execution-v2','only_alias':'os.path -> posixpath',
    'producer':['live sys.modules object chain equals os.path','canonical __name__/spec.name posixpath','origin frozen','spec and module loader identity FrozenImporter','_imp.is_frozen','exact lexical and resolved file paths and hashes for both inventory rows','live process identity','exact interpreter identity'],
    'parent':['ordinary runtime receipt verification before exemption','external context/runtime-closure/process/phase equality','current and frozen interpreter identity','canonical frozen membership','both exact inventory records and closed proof equality','boolean identities must be literal True'],
    'fresh_receipt':{'path':str(receipt_copy),'sha256':sha(receipt_copy),'original_path':str(receipts[0]),'compiled_producer':compiled[0]},
    'fresh_receipt_scope':'New real source-bootstrap process, synthetic CPU context and partial observed test inventory. Parent hashes observed inventory before handoff and independently captures PID/start ticks/boot ID. This is not production freeze or independent production source review.',
    'after_false_pass':True,'after_true_required_coverage_rejected':True,'post_episode_coverage':False,
    'ordinary_and_other_audits':'Compiled/startup enforcement retained; generated/native/_cyutility implementation unchanged. No other frozen alias exemption.'},
 'tests':tests,
 'retained_failures':[
   {'run':1,'reason':'Synthetic budget fixtures lacked task files after binding synthetic worktree. Fixed fixture to use frozen exposed task identities; run 2 passed.'},
   {'run':3,'reason':'Generated-runtime guard correctly rejected lexical TMPDIR through relocated owner symlink. Changed only test environment to resolved path under same authorized evidence directory; run 4 passed. Source-loader and new alias tests had passed in run 3.'},
   {'run':5,'reason':'Imported autouse synthetic STOP fixture leaked into release tests under /dev/null rootdir. Explicit per-module fixture marks fixed scope; run 6 passed, including positive all40 synthetic release/context and substantive mutation negatives.'},
   {'run':'8-shell-before-test','reason':'Mistyped output directory caused shell redirection failure before pytest launched. No file was created at that nonexistent path. Corrected command produced tests-8.log.'}],
 'report_builder_attempts':[{'status':'FAILED_BEFORE_REPORT_OUTPUT','reason':'pytest current-directory symlink duplicated fresh receipt glob; assert len(receipts)==1 failed. Resolved and deduplicated receipt paths; no receipt or report modified by failed attempt.'},{'status':'PASS'}],
 'validation_summary':['Independent STOP locations/files/directories/dangling symlinks/access errors and authority substitutions rejected.',
   'Independent reservation/dispatched launch races reject worker and healthcheck starts; worker pre-Main STOP retains INVALID receipt without Main.',
   'Drain/settlement and full attempt/deadline/headroom boundaries pass with synthetic processes; no real probe.',
   'Alias object/name/spec/module-loader/lexical-file/hash/interpreter substitutions rejected.',
   'Valid-shaped mismatched context/process/phase/closure bindings, missing canonical evidence, v1 receipts, arbitrary same-path aliases and missing ordinary compiled records rejected.',
   'Real source bootstrap emits v2 execution proof tied to the committed producer hash. Existing source-cache/startup and generated/native alias tests retained.',
   'git diff --check passed; committed patch matches evidence byte-for-byte; isolated checkout clean.'],
 'resource_limits':{'wall_budget_seconds':1200,'focused_tests_budget_seconds':600,'pytest_reported_seconds_total':round(sum(x[2] for x in results),2),'threads':2,'affinity':[0,1],'cuda_visible_devices':'','test_overhead':'Python startup/command overhead not separately instrumented; no long-running test or timeout.'},
 'residual_blockers':[
   {'id':'B1','status':'ENGINEERING_IMPLEMENTED_PENDING_INDEPENDENT_REVIEW_AND_NEW_FREEZE'},
   {'id':'B2','status':'FOLLOW_UP','requires':'Complete final committed source/scientific_source freeze, including permitted launcher source hash, then regenerate dependent manifests/context/reviews.'},
   {'id':'B3','status':'NARROW_ENGINEERING_PROOF_IMPLEMENTED; FULL_PRODUCTION_RECEIPTS_PENDING','requires':'Independent review and new complete process-bound receipts under final source/runtime/controller composition. CPU preflight is not post-episode coverage; other frozen aliases remain subject to ordinary executable coverage.'},
   {'id':'B4','status':'FOLLOW_UP','requires':'Immutable isolated runtime/controller checkout composition, relocated asset byte checks and full all40 production composition checks.'},
   {'id':'B5','status':'DISABLED','requires':'Separately authorized finite N36R2 admission/resource/accounting implementation and externally anchored root release; current hard rejections retained.'}],
 'accounting_preserved':{'dispatches':504,'gpu_hours':75.49265038509455,'invalid_attempts':[{'id':'n36_dev_t00_c0_001147','status':'INVALID','gpu_seconds':86.40354533703066},{'id':'n36r1_dev_t00_c0_001203','status':'INVALID','gpu_seconds':809.4826372319367}],
    'verification_scope':'Retained values from user/review. No owner ledger read, arithmetic recomputation or writes; no historical artifact modified.'},
 'scope':{'gpu':False,'simulator':False,'provider_probe':False,'packages':False,'subagents':False,'owner_state_or_ledger_writes':False,'source_adoption':False,'release_activation':False,'driver_lock':False,'coordinator_lease':False,'protected_results_read':False,'prohibited_design_read':False,'credentials_read':False,'poe_execution':False,'superpowers':False,'scientific_changes':False,
          'synthetic_locks':'Existing runner tests use only synthetic runner/state locks under evidence; no owner locks.',
          'evidence_only':str(evidence),'historical_artifacts_mutated':False},
 'release_enabled':False,'production_accepted':False,'scientific_promotion':False,'scientific_completion':False,
 'insight':'Canonical STOP authority must remain independent of checkout resolution; alias exemptions need live identity evidence joined to external process/interpreter/context bindings, not equal file hashes.',
 'code_ref':head,
}
markdown=f'''Implemented the bounded B1/B3 engineering repair in `{head}`. **Focused CPU checks pass; production remains blocked.** No scientific promotion or completion claim.

- Canonical source-bound STOP pair is independent of checkout resolution. Shared fail-closed lstat/deadline checks cover admission, healthcheck reservation/start, reservation-to-launch races, worker entry/pre-Main and next dispatch. Draining and settlement remain available without STOP signalling.
- `n36-source-execution-v2` proves only `os.path -> posixpath`: live module identity, canonical frozen spec and loaders, `_imp.is_frozen`, exact file/hash inventory, and external context/process/phase/interpreter binding. Ordinary compiled/startup and native/generated/_cyutility audits remain.
- N36R2 release/admission hard rejections remain. Owner HEAD is unchanged at `{owner_commit}`; the isolated worktree is clean and preserved. The 18-file patch is `source-changes-v1.patch`, SHA-256 `{sha(evidence/'source-changes-v1.patch')}`.

Focused results (commands, environments, log hashes and all retained failures are in the JSON):

| Run | Result | Purpose |
| --- | --- | --- |
| 1 | 18 failed / 99 passed | Synthetic worktree fixture deficiency, retained |
| 2 | 124 passed | STOP, launch races/drain, alias proof, runner, disabled N36R2 |
| 3 | 25 failed / 52 passed | Generated TMPDIR lexical-path mismatch; source-loader/alias checks passed |
| 4 | 40 passed / 6 deselected | Resolved evidence TMPDIR; _cyutility regression and pre-Main STOP |
| 5 | 1 failed / 14 passed | Imported autouse fixture scope, retained |
| 6 | 21 passed | Scoped fixture; release/context and worker boundaries |
| 7 | 38 passed | Final producer loaders/lexical paths and alias negatives |
| 8 | 23 passed / 18 deselected | Valid-shaped binding substitutions and fresh source-bootstrap receipt |

Total pytest-reported time: {sum(x[2] for x in results):.2f}s, under two-CPU affinity with CUDA hidden. One additional mistyped shell redirection failed before pytest started; no file was created there. No broad suite, real GPU/probe, simulator, provider, package installation or subagent was used.

`fresh-cpu-alias-receipt-v1.json` retains a newly executed source-bootstrap proof; its producer hash equals the committed source. It uses a synthetic CPU context and partial test inventory. `after=False` passes for that diagnostic and `after=True` rejects missing required coverage. **This is not a full production receipt, final source freeze, independent source review, or post-episode coverage.** No additional frozen alias receives an exemption.

Follow-ups remain B2 complete final source/scientific-source freeze and dependent artifacts; B4 immutable isolated runtime/controller composition and complete all40 checks; B5 finite admission/accounting/resource routing and detached approval. B1/B3 changes still require independent source review and new complete receipts. Nothing activates authority beyond `2026-10-11T11:13:13Z`.

Retained without ledger mutation: **504 dispatches / 75.49265038509455 GPUh**, INVALID N36 **86.40354533703066s**, INVALID N36R1 **809.4826372319367s**. These inherited values were not recomputed from protected/private records. Historical artifacts and earlier failures remain intact; no owner state, source adoption, release, driver lock or coordinator lease was written.

Reports completed {now.isoformat()}; elapsed wall {report['elapsed_wall_seconds']:.1f}s of 1200s. Both canonical STOP entries were absent and the deadline open at final verification; absence supplies no execution authority.
'''
with (evidence/'report-v1.md').open('x') as f:f.write(markdown)
report['markdown_sha256']=sha(evidence/'report-v1.md')
with (evidence/'report-v1.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'commit':head,'report':str(evidence/'report-v1.json'),'elapsed_wall_seconds':report['elapsed_wall_seconds'],'pytest_seconds':report['resource_limits']['pytest_reported_seconds_total']}))
