from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001743'; O=A/'turns/001740/recovery-graph-refresh'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001743');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
def git(w,*a):return subprocess.check_output(['git','-C',str(w),*a],text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();prev=json.loads((A/'turns/001742/operational-summary-v1.json').read_text()); r=json.loads((O/'report-v2.json').read_text()); e=json.loads((O/'exit-v1.json').read_text()); auth=json.loads((O/'authority-v1.json').read_text())
assert e['exit']==0 and not e['timeout']; assert r['status']=='BLOCKED_INCOMPLETE_DISABLED_GRAPH'
for pid in [3245423,3245425,3116764,3116766]:assert not Path('/proc',str(pid)).exists()
manifest=json.loads((O/'final-output-manifest-v1.json').read_text()); checked=0
for x in manifest['files']:
 p=Path(x['path']);assert p.is_relative_to(A) or p.is_relative_to(Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004')); assert 'poe' not in p.name.lower(); actual=ref(p); assert actual['sha256']==x['sha256']; assert actual['bytes']==x['bytes'];checked+=1
prefixes={}
for name,x in prev['ledger_prefixes'].items():
 actual=ref(Path(x['path']));assert actual['bytes']==x['bytes'] and actual['sha256']==x['sha256'];prefixes[name]={**actual,'prior_prefix_preserved':True}
stop=auth['stop_authority']; assert not any(Path(x).exists() for x in stop['paths']); assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
driver=json.loads((A/'driver-status.json').read_text());assert driver['turn']==1743;boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();handles={}
for k,v in {'driver':driver['driver'],'coordinator':driver['process']}.items():
 st=Path('/proc',str(v['pid']),'stat').read_text().rsplit(')',1)[1].split(); assert v['boot_id']==boot and int(st[19])==v['start_ticks'];handles[k]={**v,'observed_state':st[0],'identity_verified':True,'alive':True}
w=Path(r['source']['worktree']);assert git(w,'rev-parse','HEAD')==r['source']['commit'];assert not git(w,'status','--porcelain','--untracked-files=no')
terminal=write(T/'terminal-reconciliation-v1.json',dict(schema='n36-recovery-graph-root-reconciliation-v1',at=now,report=ref(O/'report-v2.json'),exit=ref(O/'exit-v1.json'),manifest=ref(O/'final-output-manifest-v1.json'),verified_artifacts=checked,live_executor_handles=[],status='TERMINAL_BLOCKED_INCOMPLETE_GRAPH',source=r['source'],preserved_journals=prefixes,graph_complete=False,graph_verified=False,source_edits=False,dispatch=False,blockers=r['blockers']))
diagnosis=write(T/'root-boundary-diagnosis-v1.json',dict(schema='n36-root-preparation-boundary-diagnosis-v1',at=now,standing_authority=ref(A/'user-authorization-v1.json'),terminal_reconciliation=terminal,findings=[
 {'id':'FROZEN_AUDIT_CONFLICT','evidence':'scripts/qd_ed_n36_engineering_r1.py validate_audit_view explicitly requires frozen=True together with dispatch_authority=False, release_enabled=False and all phase authorizations False.','decision':'Prior executor prompt overconstrained all frozen flags. A separately documented immutable audit-only snapshot may be frozen while all execution authorizations remain false. No existing frozen artifact or scientific threshold may be edited. This diagnosis does not freeze or adopt the current projections.'},
 {'id':'POE_FULL_SOURCE_VERIFICATION','evidence':'scripts/qd_ed_n34_source.py source_record compares listed regular tracked files against Git bytes without executing those files.','decision':'User prohibits opening/using Poe credential files and provider fallback. This does not prohibit hashing ordinary tracked implementation source such as scripts/qd_ed_poe_launch.py. Future bounded source verification may hash positively identified regular tracked code only; never import or execute the Poe launcher, resolve or open credentials, or read prohibited design/protected results. If any inventory entry is ambiguous, exclude execution and report that precise entry; do not silently omit it from attestation.'},
 {'id':'GUARDED_IMPORT_STOP','evidence':'Executor reports conservative torch import guard, not production failure.','decision':'CPU library import is distinct from loading model weights, CUDA initialization, model inference or native build. A subsequent explicitly CPU-only builder may import installed libraries with CUDA_VISIBLE_DEVICES empty, thread limits and no model/provider/native execution. This is not readiness evidence.'},
 {'id':'MISSING_EXTERNAL_CONTROLLER_ACCEPTANCE','evidence':'scripts/qd_ed_n34_controller.py verify_semantics requires ROOT_REVIEWED and three deployed_source_review bindings.','decision':'Real remaining gate: inspect only affected final runtime/closure and deployed-source evidence, independently review bindings, and root accept exact proven controller semantics before production graph composition. Never manufacture ROOT_REVIEWED to pass a validator.'}],scientific_rules_changed=False,source_changed=False,release_enabled=False,gpu_authorized=False,root_controller_acceptance=False))
next_step='Perform bounded affected controller/runtime/closure source-binding review against turn001740 proposed artifacts and exact source 89506fe; resolve genuine external controller acceptance with evidence. Apply turn001743 boundary diagnosis: immutable audit-only frozen=True is compatible with disabled execution; tracked code hashing is distinct from prohibited credential access; CPU library import is not model execution. Then create a fresh non-overwriting graph composition scope, preserve turn001730 recovery identity/prefix/costs and all41 manifest gates, independent B5 and root accounting adoption before any finite preparation release. No GPU/provider dispatch now.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1743,at=now,current_source=r['source'],owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status='CPU graph executor exited 0, terminal blocked. Prior GPU controller terminal. No live study GPU worker.',ledger_prefixes=prefixes,terminal_reconciliation=terminal,boundary_diagnosis=diagnosis,completed_work=['Verified handoff and authority hashes, driver/coordinator identity, absent STOP and open deadline.','Reconciled completed executor, verified final manifest hashes and unchanged private ledger bytes/source.','Diagnosed overbroad preparation constraints without changing source, audits, science or execution authorization; retained genuine controller acceptance gate.'],next_bounded_step=next_step,unresolved_evidence=['Final graph incomplete; all 41 manifests absent.','Affected controller/runtime/closure review, independent B5, root adoption and new measured readiness remain required.','Original validation, formal and required ablation success evidence incomplete.'],deadline_utc=stop['deadline'],stop_present=False,deadline_passed=False,target_met=False)
summary_ref=write(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:
  x=d['n36_readiness_recovery_final_graph_refresh'];x.update(status='TERMINAL_BLOCKED_INCOMPLETE_DISABLED_GRAPH',terminal_reconciliation=terminal,report=ref(O/'report-v2.json'),live_handles=[])
  for k in ['wrapper','executor']:
   if k in x:x[k].update(alive=False,identity_verified=False)
  d['n36_readiness_recovery_boundary_diagnosis']=diagnosis;d['next_action']=next_step;d['latest_operational_summary']=summary_ref;d['last_updated_utc']=now
 node=tree['nodes']['15.6'];node['result']='RECOVERY_GRAPH_TERMINAL_BLOCKED_CONTROLLER_REVIEW_REQUIRED';node['insight']=next_step;node['recovery_graph_terminal_reconciliation']=terminal
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
for x in prefixes.values():assert ref(Path(x['path']))['sha256']==x['sha256']
(T/'operational-summary-v1.sha256').write_text(summary_ref['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'summary':summary_ref,'verified_artifacts':checked,'source':r['source']['commit'],'live_handles':handles}))
