import pathlib,json,hashlib,datetime,subprocess,sys,os,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001437'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r, qd_ed_n36_contract as c, qd_ed_n36_runner as adapter

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 p=pathlib.Path('/proc')/str(pid)/'stat';s=p.read_text().rsplit(')',1)[1].split();return {'pid':pid,'start_ticks':int(s[19]),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
consumer=json.loads((out/'health-release-consumer-v1.json').read_text());assert consumer['status']=='PASS'
summary=json.loads((out/'operational-summary-v1.json').read_text())
prior=json.loads((base/'turns/001436/terminal-reconciliation-v1.json').read_text());assert prior['decision']=='ACCEPT_EXACT_CPU_B5_PENDING_ROOT_GOVERNANCE_FRESH_HEALTH'
for f in ['health-operation-process-v1.json','health-operation-launch-v1.json']:
 assert not (out/f).exists()
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=60)
  state=r.read_state(root/'research-state.yaml');assert not state['current_owned_workers']
  for v in summary['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
  assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==summary['candidate_source']
  admission=adapter.device_check();write(out/'assigned-gpu-observation-v1.json',admission)
  for pid in [1514468,1514471]:
   # Historical repair/review handles cannot be active predecessors.
   assert not (pathlib.Path('/proc')/str(pid)).exists()
  argv=[str(r.PYTHON),'-I','-S','-B','-X','pycache_prefix=/dev/null',str(source/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_healthcheck','--plan',consumer['plan']['path'],'--plan-sha256',consumer['plan']['sha256'],'--release',consumer['release']['path'],'--release-sha256',consumer['release']['sha256'],'--resource-id','n36_healthcheck_n36r3_preparation_001426']
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();intent={'schema':'n36r3-health-operation-launch-v1','argv':argv,'cwd':str(source),'plan':consumer['plan'],'release':consumer['release'],'prior_ledger_prefixes':summary['ledger_prefixes'],'prior_terminal_reconciliation':ref(base/'turns/001436/terminal-reconciliation-v1.json'),'started_at':now}
  write(out/'health-operation-intent-v1.json',intent)
  with (out/'health-wrapper.log').open('w') as log:
   p=subprocess.Popen([str(r.PYTHON),'-I','-B',str(out/'run-health-operation-v1.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=ident(p.pid);launch={**intent,'wrapper':handle};write(out/'health-operation-launch-v1.json',launch)
  nxt='Monitor turn001437 health-operation-process-v1.json exact PID/boot/start, exit/log and owning health ledger; do not duplicate or replay. Reconcile terminal resource charges and actual provider/CUDA/EGL evidence before distinct first-C0 release and mandatory G3 pause.'
  for path,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=state if isyaml else json.loads(path.read_text());d.update(n36r3_health_release_preparation={'consumer':ref(out/'health-release-consumer-v1.json'),'bindings':ref(out/'health-release-bindings-v1.json')},n36r3_live_health_operation={'launch':ref(out/'health-operation-launch-v1.json'),'wrapper':handle,'process_record_path':str(out/'health-operation-process-v1.json'),'exit_path':str(out/'health-operation-exit-v1.json'),'source':summary['candidate_source']},next_action=nxt,status='N36R3_HEALTH_OPERATION_RUNNING',phase='N36R3_HEALTH_OPERATION_RUNNING',updated_at=now)
   if isyaml:
    q=path.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,path)
   else:write(path,d)
  path=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='ACCOUNTING_HEALTH_RELEASE_ACCEPTED_HEALTH_RUNNING',n36r3_live_health_operation=ref(out/'health-operation-launch-v1.json'));write(path,d)
  summary.update(at=now,live_handles={'wrapper':handle},health_operation=ref(out/'health-operation-launch-v1.json'),next_bounded_step=nxt,unresolved_evidence=['Actual charged health readiness','First-C0 G3 review and development results','Original matched validation/formal/required ablations'])
  summary['completed_work']+=['Detached health release full production consumer passed for source d01bc1e.','Observed idle assigned GPU7 and launched one source-bootstrap health operation with durable wrapper/process/exit capture.']
  write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'wrapper':handle,'summary':ref(out/'operational-summary-v1.json')}))
