exec(open('../autonomy_20261004/turns/000572/adopt-release.py').read().split('prep=json.loads')[0])
import os
prep=json.loads((out/'n34-authority-adoption-v1.json').read_text());plan=read(prep['plan']);authority=read(prep['authority']);assert not pathlib.Path(plan['stop_path']).exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
# Read command identities only; never inspect process environments or credentials.
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try: cmd=(p/'cmdline').read_bytes().split(b'\0')
 except OSError:continue
 assert not any(x in [b'scripts.qd_ed_n34_runner',b'scripts.qd_ed_n34_worker'] or x.endswith(b'/000572/controller.py') for x in cmd), 'existing N34 process'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  s=r.read_state(root/'research-state.yaml');checkpoint=json.loads(cp.read_text());assert s['active_controller'] is None and checkpoint['active_controller'] is None;assert s['n34_budget_authority']==prep['authority']
  for n,e in authority['ledger_prefixes'].items():
   b=(root/'data'/n).read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256']
  log=(out/'controller.log').open('xb');script=out/'controller.py';argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(script)]
  proc=subprocess.Popen(argv,cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=identity(proc.pid);record={'schema':'n34-controller-launch-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'handle':handle,'argv':argv,'script':ref(script),'plan':prep['plan'],'release':prep['release'],'authority':prep['authority'],'status_path':str(out/'controller-status-v1.json'),'result_path':str(out/'controller-result-v1.json')};write(out/'controller-launch-v1.json',record)
  active={'kind':'N34_PRODUCTION_CONTROLLER','handles':{'controller':handle},'launch':ref(out/'controller-launch-v1.json'),'status_path':record['status_path'],'result_path':record['result_path'],'plan':prep['plan'],'release':prep['release']}
  for obj in [s,checkpoint]:obj.update(active_controller=active,n34_continuation_status='CONTROLLER_RUNNING_ADMISSION_PENDING')
  tmp=root/'research-state.yaml.tmp';tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(root/'research-state.yaml');write(cp,checkpoint)
  proc.stdin.write(b'G');proc.stdin.flush();proc.stdin.close()
print(json.dumps(record,indent=2))
