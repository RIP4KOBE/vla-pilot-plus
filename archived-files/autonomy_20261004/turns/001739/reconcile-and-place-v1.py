from pathlib import Path
import json,hashlib,datetime,subprocess,fcntl,os,yaml
W=Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001739'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'; O=A/'turns/001737/independent-source-review'
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def write(p,d):
 assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
def git(w,*args):return subprocess.check_output(['git','-C',str(w),*args],text=True).strip()
def atomic(p,d,y=False):
 q=p.with_name(p.name+'.tmp-001739');q.write_text(yaml.safe_dump(d,sort_keys=False) if y else json.dumps(d,indent=2)+'\n');os.replace(q,p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); prev=json.loads((A/'turns/001738/operational-summary-v1.json').read_text()); r=json.loads((O/'review-v1.json').read_text()); e=json.loads((O/'exit-v1.json').read_text()); auth=json.loads((O/'authority-v1.json').read_text())
assert ref(O/'review-v1.json')['sha256']==prev['active_executor']['review']['sha256']
assert e['exit']==0 and not e['timeout']; assert r['verdict']=='PASS_SCOPED_SOURCE_REVIEW' and not r['blocking_findings']
for pid in [3116764,3116766,3122548,3229000,3229001]:assert not Path('/proc',str(pid)).exists()
for k in ['authority','contract','specification','implementation_report','root_semantic_review','terminal_reconciliation']:
 x=r[k];assert ref(Path(x['path']))['sha256']==x['sha256']
prefixes={}
for x in r['preserved_journals']:
 p=Path(x['path']); a=ref(p); assert a['bytes']==x['bytes'] and a['sha256']==x['sha256']; prefixes[p.name]={**a,'prior_prefix_preserved':True}
stop=auth['stop_authority']; assert not any(Path(x).exists() for x in stop['paths']); assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(stop['deadline'].replace('Z','+00:00'))
driver=json.loads((A/'driver-status.json').read_text()); assert driver['turn']==1739; handles={}; boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k,v in {'driver':driver['driver'],'coordinator':driver['process']}.items():
 st=Path('/proc',str(v['pid']),'stat').read_text().rsplit(')',1)[1].split(); assert v['boot_id']==boot and int(st[19])==v['start_ticks']; handles[k]={**v,'state':st[0],'identity_verified':True}
rw=Path(r['source_after']['worktree']); source=r['source_after']['commit'];base=r['source_before']['commit'];assert git(rw,'rev-parse','HEAD')==source;assert not git(rw,'status','--porcelain','--untracked-files=no')
for f in r['source_files']:assert ref(rw/f['path'])['sha256']==f['after']['sha256']
terminal=write(T/'terminal-reconciliation-v1.json',dict(schema='n36-recovery-prefix-review-root-reconciliation-v1',at=now,review=ref(O/'review-v1.json'),exit=ref(O/'exit-v1.json'),source=source,verdict='ACCEPTED_SCOPED_CPU_SOURCE_ONLY',live_executor_handles=[],tests_reported=50,tests_rerun=False,production_ready=False,scientific_promotion=False,preserved_journals=prefixes,limitations=r['unresolved_downstream_gates']))
w=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree'); assert git(w,'rev-parse','HEAD')==base; assert not git(w,'status','--porcelain','--untracked-files=no');subprocess.run(['git','-C',str(w),'merge-base','--is-ancestor',base,source],check=True)
authority=write(T/'source-placement-authority-v1.json',dict(schema='n36-recovery-prefix-source-placement-authority-v1',at=now,standing_authority=ref(A/'user-authorization-v1.json'),review=ref(O/'review-v1.json'),terminal_reconciliation=terminal,worktree=str(w),before=base,after=source,scope='Exact independently reviewed fast-forward in isolated implementation route only. Production source adoption, release, readiness spending and GPU dispatch remain gated. Preserve untracked artifacts.',stop_authority=stop))
output=git(w,'merge','--ff-only',source); assert git(w,'rev-parse','HEAD')==source;assert not git(w,'status','--porcelain','--untracked-files=no')
for f in r['source_files']:assert ref(w/f['path'])['sha256']==f['after']['sha256']
placement=write(T/'source-placement-v1.json',dict(schema='n36-source-placement-v1',at=now,authority=authority,worktree=str(w),before=base,after=source,tree=git(w,'rev-parse','HEAD^{tree}'),tracked_clean=True,reviewed_changed_files_match=True,untracked_artifacts_preserved=True,operation_output=output,production_source_adopted=False,gpu_dispatch=False,graph_refresh_performed=False))
next_step='Refresh only affected disabled N36 readiness recovery graph at exact reviewed source 89506fe1d9e2c753b66f6d3349963f6e9b316560 in isolated adapter worktree, using turn001723 graph preparation and turn001730 canonical prospective specification/recovery-prefix contract. Keep original accounting offsets and charged aborted predecessor; explicit successor only. Generate source/runtime/closure/controller/native/scientific-equivalence/audit/manifest bindings, then independent engineering B5 and root scope/accounting adoption before any preparation release. No readiness/provider/GPU spending during CPU graph preparation; preserve STOP/deadline and original scientific gates.'
summary=dict(schema='autonomy-operational-summary-v1',turn=1739,at=now,current_source=dict(worktree=str(w),commit=source,tree=git(w,'rev-parse','HEAD^{tree}'),tracked_clean=True),owning_source=prev['owning_source'],scientific_source=prev['scientific_source'],source_adopted=False,source_placement=placement,live_handles=handles,controller_status='No live GPU controller or CPU executor; independent review exited 0 and scoped source accepted.',ledger_prefixes=prefixes,completed_work=['Verified bound authority, live driver/coordinator boot/start identities, absent STOP and open deadline.','Reconstructed successful prior turn and reviewer termination; authenticated review, source and four unchanged journals.','Accepted scoped CPU review and fast-forwarded isolated adapter worktree to exact reviewed two-file repair; production/scientific gates unchanged.'],next_bounded_step=next_step,unresolved_evidence=r['unresolved_downstream_gates'][1:],deadline_utc=stop['deadline'],stop_present=False,target_met=False)
summary_ref=write(T/'operational-summary-v1.json',summary)
with (C/'state.lock').open('a') as cl,(W/'data/qd-ed-state.lock').open('a') as rl:
 fcntl.flock(cl,fcntl.LOCK_EX);fcntl.flock(rl,fcntl.LOCK_EX)
 s=yaml.safe_load((W/'research-state.yaml').read_text());c=json.loads((C/'checkpoint.json').read_text());tree=json.loads((C/'idea_tree.json').read_text())
 for d in [s,c]:
  x=d['n36_readiness_recovery_prefix_independent_review'];x.update(status='TERMINAL_SCOPED_CPU_ROOT_ACCEPTED',terminal_reconciliation=terminal,review=ref(O/'review-v1.json'),live_handles=[])
  for key in ['wrapper','executor']:
   if key in x:x[key].update(alive=False,identity_verified=False)
  d['n36_readiness_recovery_prefix_implementation']['status']='TERMINAL_COMMITTED_SCOPED_REVIEW_ACCEPTED';d['n36_readiness_recovery_prefix_implementation']['live_handles']=[]
  d['n36_readiness_recovery_prefix_source_placement']=placement;d['active_executor']=None;d['in_flight_executor']=None;d['in_flight_executors']=[];d['next_action']=next_step;d['latest_operational_summary']=summary_ref;d['last_updated_utc']=now
 node=tree['nodes']['15.6'];node['result']='RECOVERY_PREFIX_SOURCE_ACCEPTED_PLACED_DISABLED_GRAPH_PENDING';node['insight']=next_step;node['recovery_prefix_root_reconciliation']=terminal
 atomic(W/'research-state.yaml',s,True);atomic(C/'checkpoint.json',c);atomic(C/'idea_tree.json',tree)
for x in prefixes.values():assert ref(Path(x['path']))['sha256']==x['sha256']
(T/'operational-summary-v1.sha256').write_text(summary_ref['sha256']+'  operational-summary-v1.json\n'); print(json.dumps(placement));print(json.dumps(summary_ref))
