from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,time,yaml
owner=Path.cwd(); A=(owner.parent/'autonomy_20261004').resolve(); T=A/'turns/001556'; prior=A/'turns/001555/graph-rebinding'; W=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 p=Path(p).resolve();b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
 return ref(p)
def verify(r):
 x=ref(r['path']);assert x['sha256']==r['sha256'],r['path']
 if 'bytes' in r:assert x['bytes']==r['bytes']
def ident(pid):
 f=Path(f'/proc/{pid}/stat');s=f.read_text().rsplit(')',1)[1].split();return dict(pid=pid,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(s[19]),state=s[0])
assert now<'2026-10-11T11:13:13' and not (A/'STOP').exists()
driver=json.loads((A/'driver-status.json').read_text());assert driver['turn']==1556
for k in ['driver','process']:
 live=ident(driver[k]['pid']);assert all(live[z]==driver[k][z] for z in ['pid','boot_id','start_ticks'])
s=json.loads((A/'turns/001555/operational-summary-v1.json').read_text());r=json.loads((prior/'report-v1.json').read_text());ex=json.loads((prior/'exit-v1.json').read_text())
assert ex['exit']==0 and not ex['timeout']
for h in ['wrapper','executor']:assert not Path('/proc/'+str(s['active_executor'][h]['pid'])).exists()
for x in s['ledgers'].values():verify(x)
for x in r['outputs'].values():verify(x)
for x in r['roots'].values():verify(x)
assert all(v.get('pass') is True for v in r['checks'].values())
assert r['graph_rebinding_complete'] and r['controller_verifier_compatible'] and not r['release_enabled']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==s['owner_source']
assert subprocess.check_output(['git','-C',str(W),'rev-parse','HEAD'],text=True).strip()==r['source']
review=dict(schema='n36-corrected-graph-root-terminal-review-v1',at=now,status='PASS_CPU_GRAPH_CLOSURE_PENDING_INDEPENDENT_B5',report=ref(prior/'report-v1.json'),exit=ref(prior/'exit-v1.json'),independent_b5_inputs=ref(prior/'independent-b5-inputs-v1.json'),source=r['source'],roots=r['roots'],output_hashes_verified=len(r['outputs']),checks_passed=len(r['checks']),ledger_prefixes=s['ledgers'],prior_coordinator_exit=0,recorded_executor_handles_absent=True,release_enabled=False,target_met=False,unresolved=r['unresolved'])
reviewref=put(T/'terminal-review-v1.json',review)
O=T/'independent-b5';O.mkdir()
a=dict(schema='n36-independent-b5-cpu-review-authority-v1',at=now,node_id='15.6',source=r['source'],worktree=str(W),standing_authority=ref(A/'user-authorization-v1.json'),root_terminal_review=reviewref,inputs=ref(prior/'independent-b5-inputs-v1.json'),roots=r['roots'],ledger_prefixes=s['ledgers'],timeout_seconds=1200,deadline='2026-10-11T11:13:13Z',gpu_authorized=False,source_edits_authorized=False,release_enabled=False,scope='Independent CPU-only B5 review of exact disabled preparation graph; no source, plan, runtime, owner state, scientific result, accounting, or release mutation.')
aref=put(O/'authority-v1.json',a)
prompt=f'''You are the independent B5 reviewer within an explicitly authorized continuing Arbor study, node 15.6. You did not implement or rebind this graph. Read {O/'authority-v1.json'} and hash-bound inputs. This is a bounded CPU-only review of the exact disabled graph at candidate source {r['source']} in {W}. Write artifacts only in {O}. No source edits, commits, new worktrees, dependency changes, owner state/checkpoint/tree/ledger writes, GPU use, model/provider execution, dispatch, release or adoption. Do not recursively delegate. Use only official current-login gpt-6-astra. Do not open credential files, Superpowers, or prohibited 2026-08-10-eds-qd-stage-guidance-transition-design.md. No protected validation/formal result access. Preserve all costs and frozen scientific thresholds.
Read inputs selectively from {prior/'independent-b5-inputs-v1.json'}, report and accepted recent root reviews. Independently inspect exact source contracts and refreshed graph roots: passive engineering plan/audit validation, controller proof semantics and schema, correct isolated owner/source/output paths, 40 unchanged scientific rows and gates, runtime/dependency/native provenance boundaries, manifests, finite diagnostic limits and retained ledger prefixes. Review correctness substantively, do not simply repeat preparation PASS. Reuse accepted provenance without recursive reconstruction or broad test repeats; do not run full release verifier/native loading/provider/GPU. B5 only covers preparation: worker receipts and actual readiness are future, G7 unconditional dispatch veto remains and cannot be overridden by an artifact. Distinguish errors blocking this disabled preparation from unresolved later release gates.
If justified, produce independent-b5-review-v1.json exactly matching scripts/qd_ed_n36_engineering.py validate_authority/review_bindings schema, binding the exact current graph (inspect source rather than guessing). Do not inject this review into any plan. If not justified, record specific blockers without fabricating PASS. Always produce report-v1.json including decision, evidence refs and hashes, independence, checks, blockers, future gates, source, roots, unchanged ledger checks, score:null, scientific_success:false, release_enabled:false, target_met:false. Explain whether any future controller-source change invalidates this review and requires a focused refresh. Native execution and original goal completion remain unproven. Observe STOP/deadline before work; finish within 1200 seconds. Do not request routine permission. The coordinator will reconcile your report.
'''
(O/'prompt.txt').write_text(prompt);(O/'run-executor.py').write_text((prior/'run-executor.py').read_text())
with (O/'wrapper.log').open('xb') as log:p=subprocess.Popen(['/usr/bin/python3',str(O/'run-executor.py')],cwd=W,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
put(O/'wrapper-launch-v1.json',dict(at=now,pid=p.pid,authority=aref))
for _ in range(50):
 if (O/'process-v1.json').exists():break
 time.sleep(.1)
h=json.loads((O/'process-v1.json').read_text());record=dict(status='CPU_INDEPENDENT_B5_REVIEW_RUNNING',source=r['source'],worktree=str(W),authority=aref,output_directory=str(O),process_record_path=str(O/'process-v1.json'),exit_path=str(O/'exit-v1.json'),wrapper=h['wrapper'],executor=h['executor'],gpu_authorized=False,source_edits_authorized=False,release_enabled=False)
nextstep='Monitor turn001556 independent B5 by recorded boot/start identity; reconcile exact graph review and unchanged ledgers. Then resolve G7 dispatch implementation via isolated executor and focused review before any adoption/release; actual readiness and original-goal evidence remain outstanding.'
C=owner/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isyaml in [(owner/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isyaml else json.loads(path.read_text());old=d['n36_engineering_corrected_graph_rebinding'];old['status']='TERMINAL_PASS_CPU_GRAPH_ROOT_ACCEPTED';old['terminal_review']=reviewref;d['n36_engineering_independent_b5']=record;d['active_executor']=record;d['next_action']=nextstep;d['updated_at']=now
  tmp=path.with_suffix(path.suffix+'.tmp-001556');tmp.write_text(yaml.safe_dump(d,sort_keys=False) if isyaml else json.dumps(d,indent=2)+'\n');tmp.replace(path)
 path=C/'idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='CPU_CORRECTED_GRAPH_PASS_INDEPENDENT_B5_RUNNING_NO_GPU',insight='Corrected disabled graph outputs and ledger prefixes verified; independent B5 running. Dispatch implementation, actual readiness, and original scientific goal remain unresolved.');tmp=path.with_suffix('.tmp-001556');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(path)
s.update(at=now,turn=1556,next_bounded_step=nextstep,completed_work='Reconciled prior normal coordinator and executor exits; verified corrected graph outputs/roots and preserved ledgers. Recorded root CPU-only acceptance and launched one independent official gpt-6-astra B5 reviewer.',STOP_present=False,target_met=False,active_executor=record,terminal_review=reviewref,unresolved_evidence=r['unresolved'],executor_observation=dict(status='RUNNING',release_enabled=False))
s['live_handles']=[dict(role=role,**ident(pid)) for role,pid in [('driver',driver['driver']['pid']),('coordinator',driver['process']['pid']),('wrapper',h['wrapper']['pid']),('executor',h['executor']['pid'])]]
sr=put(T/'operational-summary-v1.json',s);(T/'operational-summary-v1.sha256').write_text(sr['sha256']+'  operational-summary-v1.json\n');print(json.dumps(dict(summary=sr,terminal_review=reviewref,handles=s['live_handles'])))
