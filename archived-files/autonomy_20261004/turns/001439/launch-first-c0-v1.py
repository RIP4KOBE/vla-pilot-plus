import pathlib,json,hashlib,datetime,subprocess,sys,os,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001439'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r, qd_ed_n36_contract as c, qd_ed_n36_runner as adapter

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 s=pathlib.Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split();return {'pid':pid,'start_ticks':int(s[19]),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
consumer=json.loads((out/'first-c0-release-consumer-v1.json').read_text());assert consumer['status']=='PASS'
summary=json.loads((base/'turns/001438/operational-summary-v1.json').read_text())
assert not (out/'first-c0-operation-intent-v1.json').exists()
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=1840)
  state=r.read_state(root/'research-state.yaml');assert not state['current_owned_workers']
  assert state['status']=='N36R3_HEALTH_PASSED_FIRST_C0_RELEASE_PENDING'
  for v in summary['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
  assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==summary['candidate_source']
  driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1439
  for h in [driver['driver'],driver['process']]:assert all(ident(h['pid'])[k]==h[k] for k in ['pid','start_ticks','boot_id'])
  assert all(not pathlib.Path(f"/proc/{h['pid']}").exists() for h in summary['live_handles'].values())
  assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(r.read_events(root/'data/attempt-ledger.jsonl')).values())
  admission=adapter.device_check();write(out/'assigned-gpu-observation-v1.json',admission)
  argv=[str(r.PYTHON),'-I','-S','-B','-X','pycache_prefix=/dev/null',str(source/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_runner','--plan',consumer['plan']['path'],'--plan-sha256',consumer['plan']['sha256'],'--release',consumer['release']['path'],'--release-sha256',consumer['release']['sha256']]
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  intent={'schema':'n36r3-first-c0-operation-launch-v1','argv':argv,'cwd':str(source),'plan':consumer['plan'],'release':consumer['release'],'prior_ledger_prefixes':summary['ledger_prefixes'],'health_reconciliation':ref(base/'turns/001438/health-terminal-reconciliation-v1.json'),'started_at':now,'mandatory_boundary':'PAUSED_FOR_ROOT_G3'}
  write(out/'first-c0-operation-intent-v1.json',intent)
  with (out/'first-c0-wrapper.log').open('w') as log:
   p=subprocess.Popen([str(r.PYTHON),'-I','-B',str(out/'run-first-c0-operation-v1.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=ident(p.pid);write(out/'first-c0-operation-launch-v1.json',{**intent,'wrapper':handle})
  nxt='Monitor turn001439 first-C0 operation exact PID/boot/start, exit/log and owning ledger. No duplicate or replay. At terminal reconcile cost/native receipts and G3 acceptance before any later cell; invalidity stops cohort. Source/science frozen; validation/formal gated.'
  live={'launch':ref(out/'first-c0-operation-launch-v1.json'),'wrapper':handle,'process_record_path':str(out/'first-c0-operation-process-v1.json'),'exit_path':str(out/'first-c0-operation-exit-v1.json'),'source':summary['candidate_source'],'status':'LAUNCHED'}
  for path,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=state if isyaml else json.loads(path.read_text());d.update(n36r3_first_c0_release={'consumer':ref(out/'first-c0-release-consumer-v1.json'),'scope':ref(out/'first-c0-scope-v1.json')},n36r3_live_first_c0_operation=live,next_action=nxt,status='N36R3_FIRST_C0_RUNNING',phase='N36R3_FIRST_C0_RUNNING',updated_at=now)
   if isyaml:
    q=path.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,path)
   else:write(path,d)
  path=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='N36R3_FIRST_C0_RUNNING_G3_PENDING',n36r3_live_first_c0_operation=ref(out/'first-c0-operation-launch-v1.json'));write(path,d)
  summary.update(at=now,turn=1439,driver=driver,live_handles={'wrapper':handle},live_executor_handles=[],first_c0_operation=ref(out/'first-c0-operation-launch-v1.json'),next_bounded_step=nxt,current_observation='First-C0 adapter launched; admission and GPU worker pending.',unresolved_evidence=['First-C0 native G3 acceptance','Development promotion','Original validation/formal/required ablations'])
  summary['completed_work']=['Verified bound handoff and authority, normal prior exit, live driver/coordinator identities and unchanged private ledger prefixes.','Prepared distinct first-C0 release without changing frozen plan or source; full production release consumer passed.','Observed idle assigned GPU7; launched one adapter with mandatory first-C0 G3 pause and durable process/exit capture.']
  write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'wrapper':handle,'summary':ref(out/'operational-summary-v1.json')}))
