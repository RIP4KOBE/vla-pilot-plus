import pathlib,json,hashlib,datetime,sys,subprocess,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as r
out=root.parent/'autonomy_20261004/turns/000699';base=out.parent.parent;cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def read(v):
 assert ref(v['path'])['sha256']==v['sha256'];return json.loads(pathlib.Path(v['path']).read_text())
def write(p,v):
 tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,indent=2)+'\n');tmp.replace(p)
def identity(pid):
 a=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
 return {'pid':pid,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':int(a[19]),'state':a[0]}
prep=json.loads((out/'launch-preparation-v1.json').read_text());plan=read(prep['plan']);read(prep['release']);authority=read(prep['budget_authority']);assert ref(out/'controller.py')==prep['wrapper']
assert not pathlib.Path(plan['stop_path']).exists() and not pathlib.Path(plan['stop_path']).is_symlink();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(plan['deadline'].replace('Z','+00:00'))
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==699
for key in ['driver','process']:
 actual=identity(driver[key]['pid']);assert all(actual[k]==driver[key][k] for k in ['pid','boot_id','start_ticks'])
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==plan['source']['commit']
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:args=(p/'cmdline').read_bytes().split(b'\0')
 except OSError:continue
 assert not any(x in [b'scripts.qd_ed_n34_runner',b'scripts.qd_ed_n34_worker'] or x.endswith(b'/000572/controller.py') or x.endswith(b'/000699/controller.py') for x in args),'live N34 process'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(root/'research-state.yaml');c=json.loads(cp.read_text());assert s['active_controller'] is None and c['active_controller'] is None
  assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
  for n,e in authority['ledger_prefixes'].items():
   raw=(root/'data'/n).read_bytes();assert {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}==e
  assert not pathlib.Path(plan['stop_path']).exists() and not pathlib.Path(plan['stop_path']).is_symlink()
  script=out/'controller.py';argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(script)]
  with (out/'controller.log').open('xb') as log:proc=subprocess.Popen(argv,cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=identity(proc.pid);record={'schema':'n34-controller-launch-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handle':handle,'argv':argv,'script':ref(script),'operational_repair':ref(out/'launch-preparation-v1.json'),'plan':prep['plan'],'release':prep['release'],'authority':prep['budget_authority'],'status_path':str(out/'controller-status-v1.json'),'result_path':str(out/'controller-result-v1.json')};write(out/'controller-launch-v1.json',record)
  active={'kind':'N34_PRODUCTION_CONTROLLER','handles':{'controller':handle},'launch':ref(out/'controller-launch-v1.json'),'status_path':record['status_path'],'result_path':record['result_path'],'plan':prep['plan'],'release':prep['release']}
  for obj in [s,c]:obj.update(active_controller=active,n34_continuation_status='CONTROLLER_RUNNING_ADMISSION_PENDING',next_action='Monitor turn699 N34R9 recovery controller through frozen release revalidation and locked GPU7 admission. Never duplicate/replay. Reconcile result and ledgers before recovery.')
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,c)
  proc.stdin.write(b'G');proc.stdin.flush();proc.stdin.close()
print(json.dumps(record,indent=2))
