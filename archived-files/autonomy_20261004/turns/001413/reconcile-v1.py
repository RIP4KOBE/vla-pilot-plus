import json, pathlib, hashlib, datetime, fcntl, os, subprocess, sys, yaml
sys.dont_write_bytecode=True
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001413';review=base/'turns/001410/exact-b5-review'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_n36r3_admission as a

def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def binding(p):
 r=ref(p);return {k:r[k] for k in ['path','sha256']}
def verify(r):
 p=pathlib.Path(r['path']);assert ref(p)['sha256']==r['sha256'],str(p);return json.loads(p.read_text())
def write(p,d):
 t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(d,indent=2)+'\n');os.replace(t,p)
def live(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat'
 if not p.exists():return False
 st=p.read_text().split(') ',1)[1].split()
 return int(st[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and st[0]!='Z'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert not (base/'STOP').exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
for n,h in [('handoff-v2.json','3d8267a367e40ba6a3b9fd307fc8371a335e21bbc92df6700d7ecc10fd9669de'),('user-authorization-v1.json','a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'),('completion-contract-v1.json','4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c'),('research-continuation-v1.md','5cefad40c22cd57ac522344793c8ce734a51e9c09983d92f6ddd57dfd906710d')]:assert ref(base/n)['sha256']==h
old=json.loads((base/'turns/001412/operational-summary-v1.json').read_text()); prior=json.loads((base/'turns/001412/receipt.json').read_text());assert prior['exit']==0
assert all(not live(h) for h in [old['live_handles'][k] for k in ('wrapper','executor')])
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1413 and live(driver['driver']) and live(driver['process'])
report=json.loads((review/'report-v1.json').read_text());assert report['decision']=='PASS_PREPARATION_REQUIRES_ROOT_RELEASE' and not report['preparation_blockers']
assert json.loads((review/'executor-exit-v1.json').read_text())['exit']==0
plan=verify(report['reviewed_plan'])
for k in ['consumer_review','authority','reviewed_bindings']:verify(report[k])
assert report['source']['commit']==subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()=='4347951a24b63cdb7f0c8a585591d89f1be778ae'
assert not subprocess.check_output(['git','-C',str(source),'diff','--name-only','HEAD'],text=True).strip()
plan['b5_review']=report['consumer_review'];a.independent_review(plan)
adoption={'schema':'n36r3-source-adoption-v1','approved':True,'owner_root':str(a.OWNER),'source_cwd':str(a.SOURCE),**{k:plan[k] for k in a.BINDINGS},'independent_review':plan['b5_review']}
assert not (out/'source-adoption-v1.json').exists();write(out/'source-adoption-v1.json',adoption)
next_action='Reconcile owning state and all three journals under runner/state locks; create finite N36R3 accounting/authority using turn 001413 exact source-adoption-v1.json and accepted 001410 B5/plan. Then detached health review/release and fresh separately charged GPU7 readiness before distinct first-C0 release. Preserve mandatory first-C0 G3 pause, source 4347951 and scientific gates; no broad test repeats.'
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for r in old['ledger_prefixes'].values():
  actual=ref(pathlib.Path(r['path']));assert actual['sha256']==r['sha256'] and actual['bytes']==r['bytes']
 rec={'schema':'n36r3-exact-b5-terminal-reconciliation-v1','at':now,'decision':'ACCEPT_EXACT_B5_AND_ADOPT_SOURCE_RUNTIME_ONLY','report':binding(review/'report-v1.json'),'b5_review':report['consumer_review'],'exit':binding(review/'executor-exit-v1.json'),'source_adoption':binding(out/'source-adoption-v1.json'),'reviewed_plan':report['reviewed_plan'],'prior_handles':[old['live_handles'][k] for k in ('wrapper','executor')],'prior_handles_live':False,'driver':driver,'ledger_prefixes':old['ledger_prefixes'],'release_enabled':False,'target_met':False,'next_action':next_action}
 write(out/'terminal-reconciliation-v1.json',rec)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text())
  d['n36r3_health_binding_exact_b5_review'].update(status='TERMINAL_EXACT_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED',live_handles=[],executor_exited=True,report=rec['report'],exit=rec['exit'],terminal_reconciliation=binding(out/'terminal-reconciliation-v1.json'))
  d.update(n36r3_source_runtime_adoption=rec['source_adoption'],n36r3_health_binding_exact_b5_terminal_reconciliation=binding(out/'terminal-reconciliation-v1.json'),next_action=next_action,status='SOURCE_RUNTIME_ADOPTED_PENDING_ACCOUNTING_HEALTH',updated_at=now,phase='N36R3_SOURCE_RUNTIME_ADOPTED_PENDING_ACCOUNTING_HEALTH')
  if isinstance(d.get('active_executor'),dict) and d['active_executor'].get('output_directory')==str(review):d['active_executor']=None
  if is_yaml:
   tmp=p.with_suffix('.yaml.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
  else:write(p,d)
 p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';t=json.loads(p.read_text());t['nodes']['15.6'].update(result='REPAIRED_SOURCE_EXACT_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED_PENDING_RELEASE',insight='Exact independent B5 accepted with terminal exit 0; isolated 4347951 source/runtime adopted. Finite accounting, fresh charged readiness, actual first-C0 G3 and original scientific goals remain open.',n36r3_health_binding_exact_b5_terminal_reconciliation=binding(out/'terminal-reconciliation-v1.json'));write(p,t)
summary={'schema':'arbor-operational-summary-v1','at':now,'turn':1413,'owning_source':old['owning_source'],'candidate_source':report['source']['commit'],'source_adoption':rec['source_adoption'],'terminal_reconciliation':binding(out/'terminal-reconciliation-v1.json'),'live_executor_handles':[],'driver':driver,'ledger_prefixes':old['ledger_prefixes'],'retained_attempts':505,'retained_gpu_hours':75.52725286641478,'driver_stop_exists':False,'deadline':'2026-10-11T11:13:13Z','completed_work':['Verified bound handoff/authority/completion/continuation and prior normal turn exit.','Reconciled reviewer exit 0 and absent exact PID/start identities; owning journals unchanged.','Verified report inputs and actual exact B5 consumer; adopted isolated 4347951 source/runtime and updated owner state/checkpoint/tree.'],'next_bounded_step':next_action,'unresolved_evidence':['Locked finite accounting and fresh charged GPU/provider readiness','Actual first-C0 G3 and continuation review','Original matched validation/formal/required ablations'],'goal_complete':False}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'decision':rec['decision'],'source_adoption':rec['source_adoption'],'summary':binding(out/'operational-summary-v1.json')}))
