import pathlib,json,hashlib,datetime,subprocess,sys,shutil,time,yaml
w=pathlib.Path.cwd();o=(w.parent/'autonomy_20261004/turns/000883').resolve();v=o/'n35-protocol-review';sys.path.insert(0,str(w));from scripts import qd_ed_final_runner as runner
def read(p):return json.loads(p.read_text())
def ref(p):return dict(path=str(p.resolve()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def write(p,x):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(x,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);d=read(w.parent/'autonomy_20261004/driver-status.json');assert d['turn']==883
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for k in ['driver','process']:
 h=d[k];f=pathlib.Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(f[19])==h['start_ticks']
assert not pathlib.Path('/proc/2303352').exists();assert read(o.parent/'000882/receipt.json')['exit']==0
assert not (w.parent/'autonomy_20261004/STOP').exists();assert not pathlib.Path(read(o.parent/'000861/plan.frozen-v1.json')['stop_path']).exists()
assert now<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='969d5fb57c90f61dfc93331346f0ea8158f4eaf1'
a=read(v/'authority-v1.json')
with runner.locked(w/'data/qd-ed-runner.lock',nonblocking=True):
 with runner.locked(w/'data/qd-ed-state.lock'):
  sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
  s=runner.read_state(sp);c=read(cp);t=read(tp)
  assert not s.get('in_flight_executor') and not s.get('current_owned_workers')
  assert t['nodes']['15.5']['status']=='pending'
  for n,r in a['ledger_prefixes'].items():
   b=(w/'data'/n).read_bytes();assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
  for p in [sp,cp,tp]:shutil.copyfile(p,o/(p.name+'.retry-before'))
  assert not (v/'executor-process-v1.json').exists()
  with open(v/'wrapper.log','ab') as log:p=subprocess.Popen([sys.executable,str(v/'executor-launch-v1.py')],cwd=w,stdout=log,stderr=log,start_new_session=True)
  for _ in range(50):
   if (v/'executor-process-v1.json').exists():break
   time.sleep(.1)
  assert (v/'executor-process-v1.json').exists(),f'wrapper PID {p.pid}; reconcile before retry'
  pr=read(v/'executor-process-v1.json')
  rec=dict(status='PROTOCOL_REVIEW_RUNNING',node_id='15.5',authority=ref(v/'authority-v1.json'),process_record=ref(v/'executor-process-v1.json'),handles={k:pr[k] for k in ['wrapper','executor']},output_directory=str(v),worktree=str(w),gpu_authorized=False,source_edits_authorized=False)
  next_step='Monitor the recorded N35 independent protocol reviewer; reconcile its exact process identity and report. Review its disposition before CPU implementation authority; no GPU or protected-phase access.'
  for obj in [s,c]:obj.update(n35_protocol_review=rec,next_action=next_step,updated_at=now.isoformat())
  s.update(in_flight_executor=rec,in_flight_executors=[rec]);c.update(in_flight_executor=rec,in_flight_executors=[rec],inflight_executor=rec,inflight_executors=[rec])
  t['nodes']['15.5'].update(status='running',result='PROTOCOL_REVIEW_RUNNING_NO_GPU',protocol_review=rec)
  tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,c);write(tp,t)
  write(o/'review-dispatch-retry1-v1.json',dict(at=now.isoformat(),driver=d,review=rec,ledger_prefixes=a['ledger_prefixes'],state=ref(sp),checkpoint=ref(cp),tree=ref(tp),next_step=next_step,target_met=False))
print(json.dumps(rec))
