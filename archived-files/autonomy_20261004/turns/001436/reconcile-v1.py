import json, pathlib, hashlib, datetime, fcntl, os, subprocess, sys, yaml
sys.dont_write_bytecode=True
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001436';review=base/'turns/001433/exact-b5-review'
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def verify(r):
 p=pathlib.Path(r['path']);a=ref(p);assert a['sha256']==r['sha256'];assert 'bytes' not in r or a['bytes']==r['bytes'];return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
def live(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat'
 if not p.exists():return False
 st=p.read_text().split(') ',1)[1].split();return int(st[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and st[0]!='Z'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
for p in [base/'STOP',pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]:assert not os.path.lexists(p)
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
old=json.loads((base/'turns/001435/operational-summary-v1.json').read_text());assert json.loads((base/'turns/001435/receipt.json').read_text())['exit']==0
proc=json.loads((review/'executor-process-v1.json').read_text());assert all(not live(proc[k]) for k in ['wrapper','executor'])
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1436 and live(driver['driver']) and live(driver['process'])
r=json.loads((review/'report-v1.json').read_text());assert r['decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE' and not r['cpu_b5_blockers'];assert json.loads((review/'executor-exit-v1.json').read_text())['exit']==0
plan=verify(r['exact_plan']);verify(r['exact_bindings']);verify(r['authority']);verify(r['consumer_receipt'])
source=pathlib.Path(r['resource_routing']['source_cwd']);assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==r['source']['commit'];assert not subprocess.check_output(['git','-C',str(source),'diff','--name-only','HEAD'],text=True).strip()
sys.path.insert(0,str(source));from scripts import qd_ed_n36r3_admission as admission
plan['b5_review']={k:r['consumer_receipt'][k] for k in ['path','sha256']};admission.independent_review(plan)
next_action='Adopt exact N36R3 source d01bc1e and reviewed runtime under root governance; reconcile all three owner journals and finite accounting with retained 505 attempts / 75.53031173955723 GPUh. Bind standalone exact B5 receipt, preserve reviewed BINDINGS, and prepare detached health release with new fixed preparation ID n36_healthcheck_n36r3_preparation_001426. Execute genuine production parent attestation and charged fresh health only after governance checks. Separately release first-C0 only after valid readiness; mandatory terminal root G3 pause. No replay, later cells or protected evaluation.'
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for lr in old['ledger_prefixes'].values():assert ref(pathlib.Path(lr['path']))['sha256']==lr['sha256']
 rec={'schema':'n36r3-exact-b5-terminal-reconciliation-v1','at':now,'decision':'ACCEPT_EXACT_CPU_B5_PENDING_ROOT_GOVERNANCE_FRESH_HEALTH','report':ref(review/'report-v1.json'),'b5_review':r['consumer_receipt'],'exit':ref(review/'executor-exit-v1.json'),'process_record':ref(review/'executor-process-v1.json'),'reviewed_plan':r['exact_plan'],'prior_handles':[proc[k] for k in ['wrapper','executor']],'prior_handles_live':False,'driver':driver,'ledger_prefixes':old['ledger_prefixes'],'source_adopted':False,'release_enabled':False,'target_met':False,'retained_gpu_hours':75.53031173955723,'future_blockers':r['future_requirements_and_execution_blockers'],'preserved_failures':r['preserved_failures'],'next_action':next_action}
 write(out/'terminal-reconciliation-v1.json',rec);rr=ref(out/'terminal-reconciliation-v1.json')
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text())
  d['n36r3_accounting_health_exact_b5_review'].update(status='TERMINAL_CPU_B5_ACCEPTED_PENDING_ROOT_GOVERNANCE',live_handles=[],executor_exited=True,report=rec['report'],exit=rec['exit'],terminal_reconciliation=rr)
  for key in ['in_flight_executor','active_executor']:
   if isinstance(d.get(key),dict) and d[key].get('output_directory')==str(review):d[key]=None
  d.update(n36r3_accounting_health_exact_b5_terminal_reconciliation=rr,next_action=next_action,status='N36R3_CPU_B5_ACCEPTED_PENDING_ROOT_GOVERNANCE',updated_at=now,phase='N36R3_ROOT_GOVERNANCE_ADOPTION_REQUIRED')
  if is_yaml:
   t=p.with_suffix('.yaml.tmp');t.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(t,p)
  else:write(p,d)
 p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result='EXACT_CPU_B5_ACCEPTED_PENDING_ROOT_GOVERNANCE',insight=next_action,n36r3_accounting_health_exact_b5_terminal_reconciliation=rr);write(p,d)
summary={'schema':'arbor-operational-summary-v1','at':now,'turn':1436,'owning_source':old['owning_source'],'candidate_source':r['source']['commit'],'live_handles':[],'current_controller_status':'NO_ACTIVE_GPU_CONTROLLER_OR_REVIEWER','driver':driver,'terminal_reconciliation':rr,'ledger_prefixes':old['ledger_prefixes'],'retained_attempts':505,'retained_gpu_hours':75.53031173955723,'completed_work':['Verified bound authority, live driver identity, previous normal exit, ACTIVE/PASS isolation and unchanged private ledger prefixes.','Reconciled reviewer exit 0 and absent wrapper/executor identities; verified exact plan/bindings and actual independent_review consumer.','Accepted repaired exact CPU preparation only; current arithmetic and distinct preparation-health identity passed independent review. Updated owning state/checkpoint/tree without source adoption or dispatch.'],'next_bounded_step':next_action,'unresolved_evidence':['Root finite accounting adoption and fresh charged health execution','Current source/runtime adoption, production attestation and charged health','First-C0 native evidence and root G3','Scientific development promotion and original matched validation/formal/required ablations'],'driver_stop_exists':False,'deadline':'2026-10-11T11:13:13Z','goal_complete':False}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'decision':rec['decision'],'summary':ref(out/'operational-summary-v1.json')}))
