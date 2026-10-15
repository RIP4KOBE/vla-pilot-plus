import pathlib,json,hashlib,datetime,fcntl,os,yaml,subprocess
root=pathlib.Path.cwd(); auto=root.parent/'autonomy_20261004'; out=auto/'turns/001710'; old=json.loads((auto/'turns/001709/operational-summary-v1.json').read_text()); ex=old['executor']; ep=pathlib.Path(ex['output_directory']); now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 tmp=p.with_name(p.name+'.tmp-001710');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
exit_record=json.loads((ep/'exit-v1.json').read_text());assert exit_record['exit']==0 and not exit_record['timeout']
assert all(not (pathlib.Path('/proc')/str(ex[k]['pid'])).exists() for k in ['wrapper','executor'])
report=json.loads((ep/'report-v1.json').read_text()); manifest=json.loads((ep/'outputs-manifest-v1.json').read_text()); checked=[]
for r in manifest['artifacts']:
 p=pathlib.Path(r['path']); assert '2026-08-10-eds-qd-stage-guidance-transition-design.md' not in str(p)
 actual=ref(p);assert actual['sha256']==r['sha256'],str(p)
 if 'bytes' in r:assert actual['bytes']==r['bytes'],str(p)
 checked.append(actual)
for r in old['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))==r
wt=report['source']['worktree'];assert subprocess.check_output(['git','-C',wt,'rev-parse','HEAD'],text=True).strip()==ex['source'];assert not subprocess.check_output(['git','-C',wt,'diff','--name-only','HEAD'],text=True).strip()
assert report['release_enabled'] is False and report['production_readiness'] is False
next_step='Independently review the exact turn001707 deployed disabled graph and proposed controller semantics; obtain a detached owning-root controller binding attestation before refreshing consumers and rerunning unmodified preparation.verify_graph. Keep production and GPU release disabled; then complete exact preparation accounting/adoption/release and measured readiness gates.'
record={'schema':'n36-disabled-graph-terminal-reconciliation-v1','at':now,'decision':'TERMINAL_ARTIFACT_HASHES_VERIFIED_INDEPENDENT_GRAPH_REVIEW_AND_ROOT_ATTESTATION_PENDING','source':report['source'],'executor_exit':exit_record,'executor_handles_terminated':True,'report':ref(ep/'report-v1.json'),'outputs_manifest':ref(ep/'outputs-manifest-v1.json'),'verified_artifact_count':len(checked),'verified_artifacts':checked,'ledger_prefixes':old['ledger_prefixes'],'reported_checks':report['checks'],'remaining_exact_gates':report['remaining_exact_gates'],'independent_semantic_review_performed':False,'release_enabled':False,'gpu_authorized':False,'target_met':False,'next_bounded_step':next_step}
write(out/'terminal-reconciliation-v1.json',record); rr=ref(out/'terminal-reconciliation-v1.json')
with (root/'data/qd-ed-state.lock').open('a+') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());c=json.loads(cp.read_text());t=json.loads(tp.read_text())
 assert c['in_flight_executor']['output_directory']==str(ep)
 for d in [s,c]:
  task=d.get('n36_engineering_r1_preparation_accounting_graph_refresh',dict(ex)); task['status']=record['decision'];task['terminal_reconciliation']=rr;d['n36_engineering_r1_preparation_accounting_graph_refresh']=task
  d['n36_engineering_r1_preparation_accounting_graph_terminal_reconciliation']=rr;d['next_action']=next_step;d['last_updated_utc']=now
  if isinstance(d.get('in_flight_executor'),dict) and d['in_flight_executor'].get('output_directory')==str(ep):d['in_flight_executor']=None
 c['automatic_gpu_dispatch_authorized']=False
 node=t['nodes']['15.6'];node['result']='DISABLED_GRAPH_GENERATED_ROOT_ATTESTATION_AND_INDEPENDENT_REVIEW_PENDING';node['insight']=next_step;node['disabled_graph_terminal_reconciliation']=rr
 tmp=sp.with_name(sp.name+'.tmp-001710');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));os.replace(tmp,sp);write(cp,c);write(tp,t)
summary=dict(old);summary.update(at=now,turn=1710,driver_status=json.loads((auto/'driver-status.json').read_text()),live_executor_handles={},executor=None,executor_exit_present=True,prior_turn_status='completed_turn',completed_work=['Verified bound handoff and authorization, ACTIVE/PASS isolation and driver/coordinator identities.','Reconciled turn001707 normal exit 0; both executor processes have ended. Verified all '+str(len(checked))+' output-manifest artifact hashes and unchanged source/private ledger prefixes.','Recorded complete-graph check failure: reviewed controller semantics required. Preserved disabled release and all scientific/accounting gates; no GPU dispatch.','Updated owning state/checkpoint and active Idea Tree node under normal state lock.'],next_bounded_step=next_step,unresolved_evidence=report['remaining_exact_gates'],terminal_reconciliation=rr)
summary['stop_present']=(auto/'STOP').exists();summary['deadline_passed']=datetime.datetime.now(datetime.timezone.utc)>=datetime.datetime.fromisoformat(summary['deadline_utc'].replace('Z','+00:00'));write(out/'operational-summary-v1.json',summary)
(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'verified_artifacts':len(checked),'reconciliation':rr,'summary':ref(out/'operational-summary-v1.json'),'next_step':next_step},indent=2))
