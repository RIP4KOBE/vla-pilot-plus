import pathlib,json,hashlib,datetime,os,sys,subprocess,yaml,shutil
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000917').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tree=cp.parent/'idea_tree.json'
def ref(p):return {'path':str(p.resolve()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(r):
 p=pathlib.Path(r['path']);assert ref(p)==r;return json.loads(p.read_text())
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');tmp.replace(p)
validation=json.load(open(out/'public-release-validation-v2.json'));assert validation['status']=='PASS';plan=read(validation['plan']);release=read(validation['release']);a=read(plan['authority']);runtime=read(plan['runtime']);os.environ.update(runtime['environment']);sys.path[:0]=[str(root),str(root/'scripts')]+runtime['environment']['PYTHONPATH'].split(':')
from scripts import qd_ed_final_runner as r,qd_ed_n35_runner as runner,qd_ed_n35_release as gate
assert not pathlib.Path(plan['stop_path']).exists();assert not pathlib.Path(plan['stop_path']).is_symlink()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(a['coordinator_ends_at'].replace('Z','+00:00'))
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s,ev,res,reserv=runner.snapshot(root,a)
  assert not runner.existing_handles(plan,ev)
  assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(ev).values())
  for p in [2303352,2584850,2584851]:assert not pathlib.Path(f'/proc/{p}').exists()
  new={**s,'budget':{**s['budget'],'amendment':a['amendment']},'n35_budget_authority':plan['authority']}
  snap=gate.admission(plan,a,new,ev,res,reserv,plan['episodes'][0],now=datetime.datetime.now(datetime.timezone.utc),gpu_idle=True)
  # Admission above is CPU accounting only; actual idle GPU/provider are rechecked by runner before reservation.
  record={'schema':'n35-authority-adoption-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan':validation['plan'],'release':validation['release'],'authority':plan['authority'],'validation':ref(out/'public-release-validation-v2.json'),'accounting':snap,'gpu_dispatched':False}
  write(out/'authority-adoption-v1.json',record)
  for p in [root/'research-state.yaml',cp,tree]:shutil.copyfile(p,out/(p.name+'.before-update'))
  new.update(status='N35_RELEASE_ADOPTED_CONTROLLER_STARTING',n35_execution_release=validation['release'],n35_authority_adoption=ref(out/'authority-adoption-v1.json'),automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=a['cohort'])
  ck=json.loads(cp.read_text());ck.update(status=new['status'],n35_budget_authority=plan['authority'],n35_execution_release=validation['release'],n35_authority_adoption=ref(out/'authority-adoption-v1.json'),automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=a['cohort'])
  t=json.loads(tree.read_text());t['nodes']['15.5'].update(result='FROZEN_N35_RELEASE_PUBLIC_VALIDATION_PASS',execution_authorized=True,execution_release=validation['release'])
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(new,sort_keys=False));tmp.replace(root/'research-state.yaml');write(cp,ck);write(tree,t)
write(out/'release-refs-v1.json',{'plan':validation['plan'],'release':validation['release']})
script=(root.parent/'autonomy_20261004/turns/000861/controller.py').read_text().replace('Operational N34 wrapper repair','Operational N35 controller').replace('turns/000861','turns/000917').replace('qd_ed_n34_continuation_runner','qd_ed_n35_runner')
controller=out/'controller.py';assert not controller.exists();controller.write_text(script)
env=os.environ.copy();env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
with (out/'controller.log').open('ab',buffering=0) as log:
 p=subprocess.Popen(['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(controller)],cwd=root,env=env,stdin=subprocess.PIPE,stdout=log,stderr=log,start_new_session=True)
 stat=pathlib.Path(f'/proc/{p.pid}/stat').read_text().split(') ',1)[1].split();h={'pid':p.pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(stat[19]),'state':stat[0]}
 record={'schema':'n35-controller-launch-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handle':h,'script':ref(controller),'plan':validation['plan'],'release':validation['release'],'authority':plan['authority'],'status_path':str(out/'controller-status-v1.json'),'result_path':str(out/'controller-result-v1.json')};write(out/'controller-launch-v1.json',record)
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(root/'research-state.yaml');ck=json.loads(cp.read_text());active={'kind':'N35_CONTROLLER','handles':{'controller':h},'launch':ref(out/'controller-launch-v1.json'),**{k:record[k] for k in ['status_path','result_path','plan','release']}}
  for d in [s,ck]:d.update(active_controller=active,status='N35_CONTROLLER_RUNNING')
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False));tmp.replace(root/'research-state.yaml');write(cp,ck)
 p.stdin.write(b'G');p.stdin.close()
print(json.dumps(record))
