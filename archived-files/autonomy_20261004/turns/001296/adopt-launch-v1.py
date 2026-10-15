import pathlib,json,hashlib,datetime,os,sys,subprocess,yaml,shutil
root=pathlib.Path.cwd();out=pathlib.Path(__file__).resolve().parent;cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(v):
 p=pathlib.Path(v['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'];return json.loads(p.read_text())
def write(p,v):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
v=json.loads((out/'production-verification-v1.json').read_text());ad=json.loads((out/'locked-admission-review-v1.json').read_text())
assert v['status']=='PASS_FULL_UNMODIFIED_RELEASE_VERIFICATION' and ad['status']=='PASS_LOCKED_ACCOUNTING_DEVICE_AND_PROBE'
p=read(v['plan']);read(v['release']);a=read(p['authority']);sys.path.insert(0,p['worktree'])
from scripts import qd_ed_final_runner as r, qd_ed_n36_runner as runner
from scripts.qd_ed_n36_stop import check
check(now=datetime.datetime.now(datetime.timezone.utc),ends_at=a['coordinator_ends_at'],need=1840)
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s,ev,res,reserv=runner.snapshot(root,a)
  assert not s.get('active_controller') and not s.get('current_owned_workers') and not runner.existing_handles(p,ev)
  before=json.loads((out/'entry-reconciliation-v1.json').read_text())
  for name,record in before['owning_ledgers'].items():
   q=root/name;assert q.stat().st_size==record['bytes'] and hashlib.sha256(q.read_bytes()).hexdigest()==record['sha256']
  for q in [root/'research-state.yaml',cp]:shutil.copyfile(q,out/(q.name+'.before-adoption'))
  ck=json.loads(cp.read_text())
  for d in [s,ck]:
   d.update(n36_budget_authority=p['authority'],n36r2_execution_release=v['release'],n36_execution_release=v['release'],n36r2_production_verification=ref(out/'production-verification-v1.json'),active_plan=v['plan'],active_iteration=p['cohort'],phase='N36R2_DEV_RUNNING',status='N36R2_RELEASE_ADOPTED_CONTROLLER_STARTING',automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=p['cohort'],next_action='Monitor turn001296 single N36R2 controller and frozen runner. Do not duplicate/restart. Preserve all charges and reconcile actual terminals.',updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
  s['budget']['amendment']=a['amendment']
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False));tmp.replace(root/'research-state.yaml');write(cp,ck)
write(out/'release-refs-v1.json',{'plan':v['plan'],'release':v['release']})
with (out/'controller.log').open('ab',buffering=0) as log:
 child=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-I','-B',str(out/'controller.py')],cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=log,start_new_session=True)
 parts=pathlib.Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split();h={'pid':child.pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(parts[19]),'state':parts[0]}
 record={'schema':'n36-controller-launch-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handle':h,'script':ref(out/'controller.py'),'plan':v['plan'],'release':v['release'],'authority':p['authority'],'status_path':str(out/'controller-status-v1.json'),'result_path':str(out/'controller-result-v1.json')};write(out/'controller-launch-v1.json',record)
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(root/'research-state.yaml');ck=json.loads(cp.read_text());active={'kind':'N36_CONTROLLER','handles':{'controller':h},'launch':ref(out/'controller-launch-v1.json'),**{k:record[k] for k in ['status_path','result_path','plan','release']}}
  for d in [s,ck]:d.update(active_controller=active,status='N36R2_CONTROLLER_RUNNING')
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False));tmp.replace(root/'research-state.yaml');write(cp,ck)
 child.stdin.write(b'G');child.stdin.close()
print(json.dumps(record))
