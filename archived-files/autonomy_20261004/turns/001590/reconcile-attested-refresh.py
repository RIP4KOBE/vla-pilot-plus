import json,pathlib,hashlib,datetime,subprocess,fcntl,os,yaml
W=pathlib.Path.cwd(); A=W.parent/'autonomy_20261004'; T=A/'turns/001590'; P=A/'turns/001588/attested-consumer-refresh'; C=W/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def read(p): return json.loads(p.read_text())
def ref(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def put(p,d):
 q=p.with_name(p.name+'.tmp-001590');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def ident(v):
 q=pathlib.Path('/proc')/str(v['pid'])/'stat';a=q.read_text().rsplit(')',1)[1].split() if q.exists() else None
 ticks=int(a[19]) if a else None;match=bool(a and ticks==v['start_ticks'] and boot==v['boot_id'])
 return {**v,'observed_start_ticks':ticks,'state':a[0] if a else None,'identity_matches':match,'live':bool(match and a[0]!='Z')}
old=read(A/'turns/001589/operational-summary-v1.json'); proc=read(P/'process-v1.json'); handles={k:ident(proc[k]) for k in ['wrapper','executor']};assert not any(h['live'] for h in handles.values())
exit_record=read(P/'exit-v1.json');assert exit_record['exit']==0 and not exit_record['timeout']
checks=[]
for name,v in old['ledger_prefixes'].items():
 actual=ref(pathlib.Path(v['path']));assert actual==v;checks.append({'kind':'ledger_unchanged','reference':actual})
seal=read(P/'artifact-hash-seal-v1.json')
for v in [seal['report'],seal['independent_b5_inputs'],*seal['roots'].values()]:
 assert ref(pathlib.Path(v['path']))==v;checks.append({'kind':'sealed_artifact_verified','reference':v})
final=read(P/'artifact-final-check-v1.json');assert final['status']=='PASS' and final['all_hashes_sizes_match']
report=read(P/'report-v1.json');assert report['affected_passive_consumers_pass'] and report['controller_attestation_blocker_resolved']
state=yaml.safe_load((W/'research-state.yaml').read_text());op=state['n36_engineering_attested_consumer_refresh'];wt=pathlib.Path(op['worktree'])
owner=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip();source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=wt,text=True).strip();assert source==op['source']==old['isolated_executor_source_observed'];assert owner==old['owner_source'];assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=wt,text=True).strip()
now=datetime.datetime.now(datetime.timezone.utc).isoformat();report=read(P/'report-v1.json');assert report['release_enabled'] is False
rec=dict(schema='n36-runtime-refresh-terminal-reconciliation-v1',at=now,status='TERMINAL_ATTESTED_CONSUMERS_HASH_VERIFIED_INDEPENDENT_B5_PENDING',source=source,owner_source=owner,process=ref(P/'process-v1.json'),exit=ref(P/'exit-v1.json'),handles=handles,report=ref(P/'report-v1.json'),checks=checks,blockers=report['blockers'],remaining_obligations=[x['required_action'] for x in report['blockers']],root_attestation_performed=False,existing_root_attestation_verified=True,independent_B5_performed=False,source_adopted=False,accounting_adopted=False,gpu_dispatch=False,target_met=False)
put(T/'terminal-reconciliation-v1.json',rec)
nextstep='Obtain fresh independent B5 on turn001588/attested-consumer-refresh/independent-b5-inputs-v1.json and exact sealed roots. No prior PASS transfers. Separate protocol acceptance, source/accounting adoption, native readiness and prospective release remain required; no GPU dispatch.'
with (C/'state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for path,isyaml in [(W/'research-state.yaml',True),(C/'checkpoint.json',False)]:
  d=yaml.safe_load(path.read_text()) if isyaml else read(path);assert d['n36_engineering_attested_consumer_refresh']['process_record_path']==op['process_record_path']
  d['n36_engineering_attested_consumer_refresh']['status']=rec['status'];d['n36_engineering_attested_consumer_terminal_reconciliation']=ref(T/'terminal-reconciliation-v1.json');d['next_action']=nextstep
  if isyaml:
   q=path.with_name(path.name+'.tmp-001590');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,path)
  else: put(path,d)
 tree=read(C/'idea_tree.json');tree['nodes']['15.6'].update(result='ATTESTED_CONSUMERS_REFRESHED_INDEPENDENT_B5_PENDING',insight='CPU runtime graph refresh exited 0; sealed artifacts and six repaired source fingerprints verified at root. Prior B5 failure retained. Controller attestation and fresh independent B5 remain required; no GPU release or source/accounting adoption.');put(C/'idea_tree.json',tree)
old.update(at=now,turn=1586,live_handles=handles,driver=ident(old['driver']),prior_cohort_handles={k:ident(v) for k,v in old['prior_cohort_handles'].items()},executor_exit_exists=True,stop_exists=(A/'STOP').exists(),next_bounded_step=nextstep,terminal_reconciliation=ref(T/'terminal-reconciliation-v1.json'),completed_work=['Verified bound handoff and authority, driver identity, normal prior coordinator completion and private ledger prefixes.','Reconciled CPU executor normal terminal exit; verified sealed artifact bytes/hashes and refreshed roots and affected-consumer PASS report.','Updated owning state, checkpoint and node with terminal refresh status and exact outstanding gates.'],unresolved_evidence=[x['required_action'] for x in report['blockers']]+['Original validation/formal/required ablation completion remains unestablished.'])
old.pop('executor_events_bytes',None);put(T/'operational-summary-v1.json',old);(T/'operational-summary-v1.sha256').write_text(ref(T/'operational-summary-v1.json')['sha256']+'\n')
print(json.dumps({'status':rec['status'],'checks':len(checks),'handles':handles,'summary':ref(T/'operational-summary-v1.json')},indent=2))
