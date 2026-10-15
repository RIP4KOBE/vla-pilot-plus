import pathlib,json,hashlib,datetime,sys,subprocess,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=(root.parent/'autonomy_20261004/turns/000861').resolve();cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';sp=root/'research-state.yaml'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(v):
 assert ref(v['path'])==v;return json.loads(pathlib.Path(v['path']).read_text())
def write(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def identity(pid):
 a=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(a[19]),'state':a[0]}
prep=json.loads((out/'release-refs-v1.json').read_text());plan=read(prep['plan']);read(prep['release']);a=read(plan['authority']);v=json.loads((out/'public-release-validation-v1.json').read_text());assert v['status']=='PASS' and v['plan']==prep['plan'] and v['release']==prep['release']
assert not pathlib.Path(plan['stop_path']).exists() and not pathlib.Path(plan['stop_path']).is_symlink();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(plan['deadline'].replace('Z','+00:00'))
driver=json.loads((out.parent.parent/'driver-status.json').read_text());assert driver['turn']==861
for key in ['driver','process']:
 actual=identity(driver[key]['pid']);assert all(actual[k]==driver[key][k] for k in ['pid','boot_id','start_ticks'])
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(b'\0')
 except OSError:continue
 assert not any(x in [b'scripts.qd_ed_n34_runner',b'scripts.qd_ed_n34_continuation_runner',b'scripts.qd_ed_n34_worker'] or x.endswith(b'/000721/controller.py') or x.endswith(b'/000861/controller.py') for x in args),'live N34 process'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(sp);c=json.loads(cp.read_text())
  for obj in [s,c]:
   old=obj['active_controller'];assert old['terminal_status']=='BUDGET_CAPPED_PARTIAL_COHORT_NO_PROMOTION' and old['live_handles']==[]
  assert not s['current_owned_workers'];assert not pathlib.Path('/proc/1322966').exists()
  assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
  for n,e in a['ledger_prefixes'].items():
   raw=(root/'data'/n).read_bytes();assert {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}==e
  assert s['n34_budget_authority']==a['previous_authority']
  for f in [sp,cp]:shutil.copyfile(f,out/(f.name+'.before'))
  write(out/'authority-adoption-v1.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),authority=plan['authority'],plan=prep['plan'],release=prep['release'],validation=ref(out/'public-release-validation-v1.json'),accounting=a['accounting_review'],ledger_prefixes=a['ledger_prefixes'],historical_costs_preserved=True))
  s['budget']['amendment']=a['amendment']
  for obj in [s,c]:obj.update(closed_n34r11_controller=obj['active_controller'],active_controller=None,n34_continuation_budget_authority=plan['authority'],n34_continuation_frozen_plan=prep['plan'],n34_continuation_execution_release=prep['release'],n34_continuation_authority_adoption=ref(out/'authority-adoption-v1.json'),automatic_gpu_dispatch_authorized=True,automatic_gpu_dispatch_scope=plan['label'],status='N34_CONTINUATION11_RELEASE_ADOPTED')
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c)
  assert not pathlib.Path(plan['stop_path']).exists()
  script=out/'controller.py';argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(script)]
  with (out/'controller.log').open('xb') as log:proc=subprocess.Popen(argv,cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=identity(proc.pid);record={'schema':'n34-continuation-controller-launch-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handle':handle,'argv':argv,'script':ref(script),'plan':prep['plan'],'release':prep['release'],'authority':plan['authority'],'status_path':str(out/'controller-status-v1.json'),'result_path':str(out/'controller-result-v1.json')};write(out/'controller-launch-v1.json',record)
  active={'kind':'N34_CONTINUATION11_CONTROLLER','handles':{'controller':handle},'launch':ref(out/'controller-launch-v1.json'),'status_path':record['status_path'],'result_path':record['result_path'],'plan':prep['plan'],'release':prep['release']}
  for obj in [s,c]:obj.update(active_controller=active,n34_continuation_status='CONTROLLER_RUNNING_ADMISSION_PENDING',next_action='Monitor turn861 continuation11 controller through release revalidation and locked GPU7 admission. Never replay retained19 or duplicate dispatch. Frozen outcome-aware Dev screen only; root scientific review required before any protected evaluation.')
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c)
  proc.stdin.write(b'G');proc.stdin.flush();proc.stdin.close()
print(json.dumps(record))
