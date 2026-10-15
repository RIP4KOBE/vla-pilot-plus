import pathlib,json,hashlib,datetime,subprocess,sys,os,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001611'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r, qd_ed_n36_contract as c, qd_ed_n36_runner as adapter

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
def ident(pid):
 p=pathlib.Path('/proc')/str(pid)/'stat';s=p.read_text().rsplit(')',1)[1].split();return {'pid':pid,'start_ticks':int(s[19]),'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
consumer=json.loads((out/'episode-release-consumer-v1.json').read_text());assert consumer['status']=='PASS'
summary=json.loads((base/'turns/001610/operational-summary-v1.json').read_text());summary['candidate_source']=summary['current_source'];summary['turn']=1611
assert json.loads((base/'turns/001608/pre-release-closure-v2.json').read_text())['decision']=='PASS'
for f in ['episode-operation-process-v1.json','episode-operation-launch-v1.json']:
 assert not (out/f).exists()
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1611
for key in ['driver','process']:
 h=driver[key];assert ident(h['pid'])=={k:h[k] for k in ['pid','start_ticks','boot_id']}
summary['driver']=driver['driver'];summary['coordinator']=driver['process']
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=2100)
  state=r.read_state(root/'research-state.yaml');assert not state['current_owned_workers']
  for v in summary['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
  assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==summary['candidate_source']
  admission=adapter.device_check();write(out/'assigned-gpu-observation-v1.json',admission)
  argv=[str(r.PYTHON),'-I','-S','-B','-X','pycache_prefix=/dev/null',str(source/'scripts/qd_ed_n36_bootstrap.py'),'scripts.qd_ed_n36_engineering','--plan',consumer['plan']['path'],'--plan-sha256',consumer['plan']['sha256'],'--release',consumer['release']['path'],'--release-sha256',consumer['release']['sha256']]
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();intent={'schema':'n36r3-episode-operation-launch-v1','argv':argv,'cwd':str(source),'plan':consumer['plan'],'release':consumer['release'],'prior_ledger_prefixes':summary['ledger_prefixes'],'prior_terminal_reconciliation':ref(base/'turns/001610/health-terminal-reconciliation-v1.json'),'started_at':now}
  write(out/'episode-operation-intent-v1.json',intent)
  with (out/'episode-wrapper.log').open('w') as log:
   p=subprocess.Popen([str(r.PYTHON),'-I','-B',str(out/'run-episode-operation-v1.py')],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  handle=ident(p.pid);launch={**intent,'wrapper':handle};write(out/'episode-operation-launch-v1.json',launch)
  nxt='Monitor turn001611 episode-operation-process-v1.json exact PID/boot/start, exit/log and owning episode ledger; do not duplicate or replay. Reconcile terminal charge, native audits and first-C0 G3 evidence. No scientific promotion or further dispatch without the frozen gates.'
  for path,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=json.loads(json.dumps(state)) if isyaml else json.loads(path.read_text());d.update(n36_engineering_episode_release_preparation={'consumer':ref(out/'episode-release-consumer-v1.json'),'bindings':ref(out/'root-episode-review-v1.json')},n36_engineering_live_episode_operation={'launch':ref(out/'episode-operation-launch-v1.json'),'wrapper':handle,'process_record_path':str(out/'episode-operation-process-v1.json'),'exit_path':str(out/'episode-operation-exit-v1.json'),'source':summary['candidate_source']},next_action=nxt,status='N36_ENGINEERING_EPISODE_OPERATION_RUNNING',phase='N36_ENGINEERING_EPISODE_OPERATION_RUNNING',updated_at=now)
   if isyaml:
    q=path.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,path)
   else:write(path,d)
  path=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(path.read_text());d['nodes']['15.6'].update(result='ACCOUNTING_EPISODE_RELEASE_ACCEPTED_EPISODE_RUNNING',n36_engineering_live_episode_operation=ref(out/'episode-operation-launch-v1.json'));write(path,d)
  summary.update(at=now,gpu_dispatch_this_turn=True,gpu_dispatch=True,ledgers_unchanged=False,live_handles={'wrapper':handle},episode_operation=ref(out/'episode-operation-launch-v1.json'),next_bounded_step=nxt,unresolved_evidence=['Actual engineering episode result and native audits','First-C0 G3 review and development results','Original matched validation/formal/required ablations'])
  summary['completed_work']+=['Detached engineering episode release production consumer passed for source b8d6b981.','Observed idle assigned GPU7 and launched one source-bootstrap episode operation with durable wrapper/process/exit capture.']
  write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'wrapper':handle,'summary':ref(out/'operational-summary-v1.json')}))
