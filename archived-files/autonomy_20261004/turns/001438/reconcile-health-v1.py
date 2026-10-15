import json,pathlib,hashlib,datetime,os,sys,yaml,subprocess
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001438';prior=base/'turns/001437'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r
def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
def observe(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else None
 return {**h,'live':bool(v and int(v[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and v[0]!='Z'),'observed_state':v[0] if v else None}
old=json.loads((prior/'operational-summary-v1.json').read_text());driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1438
assert observe(driver['driver'])['live'] and observe(driver['process'])['live']
handles={k:observe(v) for k,v in old['live_handles'].items()};assert not any(v['live'] for v in handles.values())
exitrec=json.loads((prior/'health-operation-exit-v1.json').read_text());assert exitrec['exit']==0
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==old['candidate_source']
nextstep='Prepare separately scoped first-C0 N36R3 execution release from frozen turn001437 plan/source d01bc1e using completed health n36_healthcheck_n36r3_preparation_001426 and turn001438 reconciliation. Verify production release consumer, STOP/deadline, ledger accounting and GPU7 idle admission before one controller launch; mandatory G3 pause after first C0. No health replay, automatic recovery, scientific edits, validation or formal access.'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  anchors={};rows={}
  for n,v in old['ledger_prefixes'].items():
   p=pathlib.Path(v['path']);b=p.read_bytes();assert hashlib.sha256(b[:v['bytes']]).hexdigest()==v['sha256'];anchors[n]={**ref(p),'prior_prefix_preserved':True};rows[n]=[json.loads(x) for x in b.splitlines() if x.strip()]
  health=[x for x in rows['gpu-healthcheck-ledger.jsonl'] if x.get('resource_id')=='n36_healthcheck_n36r3_preparation_001426'];assert [x['event'] for x in health]==['reserved','dispatched','completed']
  terminal=health[-1];assert terminal['validation_status']=='passed' and terminal['provider_verified'] is True and terminal['gpu_uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187'
  result=pathlib.Path(terminal['output_dir'])/'healthcheck-result.json';assert json.loads(result.read_text())==terminal
  snap=r.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']);assert snap['running']==snap['gpu_healthcheck_inflight']==0 and snap['dispatched']==505
  assert abs(snap['gpu_hours_consumed']-(old['retained_gpu_hours']+terminal['gpu_process_wall_seconds']/3600))<1e-10
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  rec={'schema':'n36r3-health-terminal-reconciliation-v1','at':now,'status':'PASS_HEALTH_COMPLETED_FIRST_C0_RELEASE_PENDING','source':old['candidate_source'],'handles':handles,'exit':ref(prior/'health-operation-exit-v1.json'),'result':ref(result),'terminal_event':terminal,'ledger_prefixes':anchors,'snapshot':snap,'previous_gpu_hours':old['retained_gpu_hours'],'added_gpu_hours':terminal['gpu_process_wall_seconds']/3600,'no_episode_dispatched':True,'next_action':nextstep,'goal_complete':False};write(out/'health-terminal-reconciliation-v1.json',rec)
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(n36r3_health_terminal_reconciliation=ref(out/'health-terminal-reconciliation-v1.json'),budget_snapshot=snap,next_action=nextstep,status='N36R3_HEALTH_PASSED_FIRST_C0_RELEASE_PENDING',phase='N36R3_HEALTH_PASSED_FIRST_C0_RELEASE_PENDING',updated_at=now)
   if isyaml:
    d['budget']['gpu_hours_consumed']=snap['gpu_hours_consumed'];tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';tree=json.loads(p.read_text());tree['nodes']['15.6'].update(n36r3_health_terminal_reconciliation=ref(out/'health-terminal-reconciliation-v1.json'),result='N36R3_HEALTH_PASSED_FIRST_C0_RELEASE_PENDING',insight=nextstep);write(p,tree)
summary={'schema':'arbor-operational-summary-v1','at':now,'turn':1438,'owning_source':old['owning_source'],'candidate_source':old['candidate_source'],'live_handles':handles,'driver':driver,'current_controller_status':'HEALTH_EXIT_0_NO_EPISODE_CONTROLLER','ledger_prefixes':anchors,'retained_attempts':505,'retained_gpu_hours':snap['gpu_hours_consumed'],'completed_work':['Verified bound handoff/authority, live driver/coordinator identities and historical ledger prefixes.','Monitored existing health operation through exit 0 without replay or duplicate dispatch.','Confirmed actual provider/CUDA/EGL health PASS on assigned GPU7 UUID and reconciled 10.950214579002932 GPU-seconds under owner operation locks.'],'terminal_reconciliation':ref(out/'health-terminal-reconciliation-v1.json'),'next_bounded_step':nextstep,'unresolved_evidence':['First-C0 production release and mandatory G3 review','Fresh matched development outcomes and scientific promotion','Original matched validation/formal/required ablations'],'driver_stop_exists':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z','goal_complete':False}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(json.dumps({'status':rec['status'],'snapshot':snap,'summary':ref(out/'operational-summary-v1.json')}))
