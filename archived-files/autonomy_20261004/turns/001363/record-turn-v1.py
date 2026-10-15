import json,pathlib,hashlib,datetime,sys,os,subprocess,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001363';old=json.loads((base/'turns/001362/operational-summary-v1.json').read_text())
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree');sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
result=json.loads((out/'health-release-consumer-v2.json').read_text())
now=datetime.datetime.now(datetime.timezone.utc).isoformat();driver=json.loads((base/'driver-status.json').read_text());handles={}
for k in ['driver','process']:
 v=driver[k];p=pathlib.Path('/proc')/str(v['pid'])/'stat';a=p.read_text().split();assert a[21]==str(v['start_ticks']);handles[k]={**v,'state':a[2]}
gpu=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True)
assigned=[line for line in gpu.splitlines() if line.startswith('GPU-48473162-9548-1a19-04aa-ea86c5349187')]
write(out/'assigned-gpu-observation-v1.json',{'at':now,'assigned_uuid':'GPU-48473162-9548-1a19-04aa-ea86c5349187','processes':assigned,'read_only':True,'dispatch_permitted':False})
nextstep=('Monitor assigned GPU7 until idle without preemption; then run one fresh charged N36R3 healthcheck via frozen source bootstrap using turn001363 plan.frozen-v2 and health-release-v2. Separate first-C0 release requires successful readiness, then mandatory G3 pause.' if result['status']=='PASS' else 'Diagnose turn001363 full health-release consumer failure from health-release-consumer-v2.json; do not dispatch. Assigned GPU7 is occupied. Preserve source and all ten B5 bindings.')
status='HEALTH_RELEASE_VERIFIED_WAIT_ASSIGNED_GPU_IDLE' if result['status']=='PASS' else 'HEALTH_RELEASE_CONSUMER_BLOCKED_NO_DISPATCH'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  for v in old['ledger_prefixes'].values():assert pathlib.Path(v['path']).stat().st_size==v['bytes'] and ref(pathlib.Path(v['path']))['sha256']==v['sha256']
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text())
   if isyaml:assert not d['current_owned_workers']
   d.update(status=status,next_action=nextstep,updated_at=now,n36r3_health_release_preparation={'consumer':ref(out/'health-release-consumer-v2.json'),'bindings':ref(out/'health-release-bindings-v2.json'),'gpu_observation':ref(out/'assigned-gpu-observation-v1.json'),'gpu_dispatched':False})
   if isyaml:
    tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result=status,n36r3_health_release_consumer=ref(out/'health-release-consumer-v2.json'));write(p,d)
summary={**old,'at':now,'turn':1363,'driver':driver,'live_handles':handles,'live_executor_handles':[],'completed_work':['Reconciled normal prior turn, absent prior executor handles and unchanged private ledger prefixes.','Prepared detached health release, preserving source/science/B5 bindings. Retained failed preparation and consumer records; supplied existing inventory/seed metadata in new v2 plan.','Full production health-release consumer: '+result['status']+'. No GPU dispatch or ledger charge.'],'health_release_consumer':ref(out/'health-release-consumer-v2.json'),'assigned_gpu_observation':ref(out/'assigned-gpu-observation-v1.json'),'next_bounded_step':nextstep,'unresolved_evidence':['Assigned GPU7 idle admission and fresh charged provider/CUDA/EGL readiness','First C0 production G3 and continuation review','Original validation/formal/required ablation completion'],'goal_complete':False}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n');print(status)
