import pathlib,json,hashlib,datetime,os,sys,yaml
root=pathlib.Path.cwd(); base=root.parent/'autonomy_20261004'; out=base/'turns/001415'; previous=base/'turns/001414'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as runner
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
def live(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat'
 if not p.exists():return False
 a=p.read_text().rsplit(')',1)[1].split();return int(a[19])==int(h.get('start_ticks',h.get('proc_start_ticks'))) and h['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip() and a[0]!='Z'
old=json.loads((previous/'operational-summary-v1.json').read_text()); driver=json.loads((base/'driver-status.json').read_text())
assert driver['turn']==1415 and live(driver['driver']) and live(driver['process'])
assert json.loads((previous/'receipt.json').read_text())['exit']==0
assert json.loads((previous/'health-operation-exit-v1.json').read_text())['exit']==0
assert all(not live(h) for h in old['live_handles'].values())
for name,digest in [('completion-contract-v1.json','4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c'),('research-continuation-v1.md','5cefad40c22cd57ac522344793c8ce734a51e9c09983d92f6ddd57dfd906710d')]:assert ref(base/name)['sha256']==digest
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
nextstep='Prepare and validate distinct first-C0 N36R3 release from frozen turn001414 plan/release plus turn001415 health terminal reconciliation; recheck STOP/deadline and idle assigned GPU7 before dispatch. Mandatory G3 pause after first C0. Do not repeat healthcheck, replay old attempts or alter frozen source/scientific gates.'
with runner.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(root/'data/qd-ed-state.lock'):
  anchors={};rows={}
  for name,v in old['ledger_prefixes'].items():
   p=pathlib.Path(v['path']);b=p.read_bytes();assert hashlib.sha256(b[:v['bytes']]).hexdigest()==v['sha256']; anchors[name]={**ref(p),'prior_prefix_preserved':True};rows[name]=[json.loads(l) for l in b.splitlines()]
  assert anchors['attempt-ledger.jsonl']['sha256']==old['ledger_prefixes']['attempt-ledger.jsonl']['sha256']
  health=[e for e in rows['gpu-healthcheck-ledger.jsonl'] if e.get('resource_id')=='n36_healthcheck_n36r3_preparation_001314'];assert [e['event'] for e in health]==['reserved','dispatched','completed']
  result=health[-1]; rp=pathlib.Path(result['output_dir'])/'healthcheck-result.json';assert json.loads(rp.read_text())==result
  hp=json.loads((rp.parent/'process.json').read_text()); assert not live(hp)
  assert result['validation_status']=='passed' and result['provider_verified'] and result['source_commit']==old['candidate_source']
  for key in ['plan','release','runtime','protocol','accounting']:
   assert ref(pathlib.Path(result[key]['path']))['sha256']==result[key]['sha256']
  assert result['physical_gpu']==7 and result['gpu_uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187'
  assert result['gpu_process_wall_seconds']<=result['reserved_gpu_seconds']
  snap=runner.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']);assert snap['running']==snap['gpu_healthcheck_inflight']==0
  assert abs(snap['gpu_hours_consumed']-old['retained_gpu_hours']-result['gpu_process_wall_seconds']/3600)<1e-10
  rec={'schema':'n36r3-health-terminal-reconciliation-v1','at':now,'status':'PASS_HEALTH_READY_FIRST_C0_RELEASE_PENDING','source':old['candidate_source'],'exit':ref(previous/'health-operation-exit-v1.json'),'terminal':ref(rp),'process':ref(rp.parent/'process.json'),'handles_absent':True,'ledger_prefixes':anchors,'new_health_events':3,'episode_ledger_unchanged':True,'gpu_seconds_charged':result['gpu_process_wall_seconds'],'increment_gpu_hours':result['gpu_process_wall_seconds']/3600,'snapshot':snap,'provider_verified':True,'cuda_egl_verified':True,'no_new_dispatch':True,'validation_formal_authorized':False,'goal_complete':False,'next_action':nextstep}
  write(out/'terminal-reconciliation-v1.json',rec)
  summary={**old,'at':now,'turn':1415,'driver':driver,'terminal_reconciliation':ref(out/'terminal-reconciliation-v1.json'),'ledger_prefixes':anchors,'retained_attempts':snap['dispatched'],'retained_gpu_hours':snap['gpu_hours_consumed'],'live_handles':{},'live_executor_handles':[],'current_observation':'Health completed VALID; wrapper, parent and GPU child absent. No episode dispatched.','completed_work':['Verified handoff/authority and driver identities; prior turn exited normally.','Verified immutable ledger prefixes and frozen health artifact bindings.','Reconciled one reserved/completed health operation: CUDA/EGL and provider passed; all 11.011943312827498 GPU seconds retained.','Preserved 505 attempts and protected reserves; no scientific source changes or protected evaluation.'],'next_bounded_step':nextstep,'unresolved_evidence':['Distinct first-C0 release and mandatory G3 native review','Development promotion','Original validation/formal/required ablations'],'driver_stop_exists':(base/'STOP').exists(),'goal_complete':False}
  write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
  runner.sync_state_from_journal(root,rows['attempt-ledger.jsonl'])
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(status=rec['status'],phase=rec['status'],next_action=nextstep,updated_at=now,n36r3_health_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'),latest_operational_summary=ref(out/'operational-summary-v1.json'))
   d['n36r3_live_health_operation'].update(status='COMPLETED_VALID',live_handles=[],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'))
   if isyaml:
    tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(n36r3_health_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'),result=rec['status']);write(p,d)
print(json.dumps({'status':rec['status'],'gpu_hours':snap['gpu_hours_consumed'],'summary':ref(out/'operational-summary-v1.json')}))
