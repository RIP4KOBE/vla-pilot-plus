from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001722';C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator';O=A/'turns/001721/independent-import-review'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def git(w,*args):return subprocess.check_output(['git','-C',str(w),*args],text=True).strip()
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001722');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();prev=json.loads((A/'turns/001721/operational-summary-v1.json').read_text());r=json.loads((O/'review-v1.json').read_text());e=json.loads((O/'exit-v1.json').read_text());proc=json.loads((O/'process-v1.json').read_text())
assert e['exit']==0 and not e['timeout'];assert r['verdict']=='PASS_SCOPED_CPU' and not r['blocking_findings'];assert (O/'review-v1.json.sha256').read_text().split()[0]==ref(O/'review-v1.json')['sha256']
for k in ['wrapper','executor']:assert not Path('/proc',str(proc[k]['pid'])).exists()
for k in ['authority','repair_report']:
 x=r[k];assert ref(Path(x['path']))['sha256']==x['sha256']
rw=Path(r['source']['worktree']);source=r['source']['commit'];assert git(rw,'rev-parse','HEAD')==source
for f in r['source']['files']:assert ref(rw/f['path'])['sha256']==f['after_sha256']
for x in r['source']['runtime_audit_dependency_hashes']:assert ref(Path(x['path']))['sha256']==x['sha256']
prefixes={}
for k,v in prev['ledger_prefixes'].items():
 p=Path(v['path']);assert hashlib.sha256(p.read_bytes()[:v['bytes']]).hexdigest()==v['sha256'];prefixes[k]={**ref(p),'prior_prefix_preserved':True}
stop=json.loads((A/'turns/001694/preparation-accounting-repair/prospective-release-v1.json').read_text())['stop_authority'];assert not any(Path(x).exists() for x in stop['paths']);assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
driver=json.loads((A/'driver-status.json').read_text());handles={};boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k,v in {'driver':driver['driver'],'coordinator':driver['process']}.items():
 s=Path('/proc',str(v['pid']),'stat').read_text().rsplit(')',1)[1].split();assert v['boot_id']==boot and int(s[19])==v['start_ticks'];handles[k]={**v,'state':s[0],'identity_verified':True}
terminal=write(T/'terminal-reconciliation-v1.json',dict(schema='n36-import-review-root-reconciliation-v1',at=now,review=ref(O/'review-v1.json'),exit=ref(O/'exit-v1.json'),source=source,verdict='ACCEPTED_SCOPED_CPU',tests_independently_reported=62,live_executor_handles=[],runtime_ready=False,scientific_promotion=False,retained_consumed_resource=r['consumed_resource']))
w=Path(prev['current_source']['worktree']);base=r['source']['base_commit'];assert git(w,'rev-parse','HEAD')==base;assert not git(w,'status','--porcelain','--untracked-files=no');subprocess.run(['git','-C',str(w),'merge-base','--is-ancestor',base,source],check=True)
authority=write(T/'source-placement-authority-v1.json',dict(schema='n36-import-repair-source-placement-authority-v1',at=now,standing_authority=ref(A/'user-authorization-v1.json'),review=ref(O/'review-v1.json'),terminal_reconciliation=terminal,worktree=str(w),before=base,after=source,scope='Exact reviewed fast-forward only. No scientific change, source adoption, release, measurement, provider or GPU dispatch. Preserve untracked CPU artifacts.',stop_authority=stop))
output=git(w,'merge','--ff-only',source);assert git(w,'rev-parse','HEAD')==source;assert not git(w,'status','--porcelain','--untracked-files=no')
for f in r['source']['files']:assert ref(w/f['path'])['sha256']==f['after_sha256']
placement=write(T/'source-placement-v1.json',dict(schema='n36-source-placement-v1',at=now,authority=authority,worktree=str(w),before=base,after=source,tree=git(w,'rev-parse','HEAD^{tree}'),tracked_clean=True,untracked_cpu_artifacts_preserved=True,reviewed_changed_files_match=True,operation_output=output,source_adopted=False,gpu_dispatch=False,graph_refresh_performed=False))
next_step='Prepare a fresh prospective N36 readiness recovery identity and disabled graph at reviewed source 1c10f9dd2afed8f8301e61f42dde46b8fa9565ed, using the existing turn001707 graph-generation workflow with only affected source/identity paths refreshed. Bind retained 0.045194898711310494 GPUh preparation failure; never replay n36_readiness_preparation_001651. Independently review affected bindings before finite release or measurement; runtime readiness and all scientific promotion gates remain closed.'
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:
  for key in ['n36_readiness_import_repair','n36_readiness_import_repair_review']:
   d[key]['status']='TERMINAL_SCOPED_CPU_ROOT_ACCEPTED';d[key]['terminal_reconciliation']=terminal;d[key]['live_handles']=[]
  d['n36_readiness_import_repair_review']['review']=ref(O/'review-v1.json');d['n36_readiness_import_source_placement']=placement;d['in_flight_executor']=None;d['in_flight_executors']=[];d['next_action']=next_step;d['last_updated_utc']=now
 node=tree['nodes']['15.6'];node['result']='IMPORT_REPAIR_SCOPED_CPU_ACCEPTED_FRESH_READINESS_RECOVERY_PENDING';node['insight']=next_step;node['import_repair_root_reconciliation']=terminal
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
summary=dict(schema='autonomy-operational-summary-v1',turn=1722,at=now,current_source=dict(worktree=str(w),commit=source,tree=git(w,'rev-parse','HEAD^{tree}'),tracked_clean=True),owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],live_handles=handles,controller_status='No live review or measurement controller. Prior preparation remains aborted and charged. Reviewed repair placed; no GPU dispatch.',ledger_prefixes=prefixes,completed_work=['Verified bound authority, driver identities, STOP/deadline and unchanged private ledger prefixes.','Reconciled independent PASS_SCOPED_CPU review: 62 checks, no blocking findings, exact source/dependency hashes verified.','Fast-forwarded isolated implementation route to exact reviewed commit; updated owning state, checkpoint and Idea Tree without modifying scientific source or gates.'],next_bounded_step=next_step,unresolved_evidence=['Fresh recovery identity, affected graph bindings and finite release remain pending.','Native/runtime readiness remains unproved.','Original validation/formal/required ablation completion remains unproved; unknown telemetry retained.'],deadline_utc=stop['deadline'],stop_present=False,target_met=False)
write(T/'operational-summary-v1.json',summary);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps(placement));print(json.dumps(ref(T/'operational-summary-v1.json')))
