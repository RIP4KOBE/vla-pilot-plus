import json,pathlib,hashlib,datetime,fcntl,os,subprocess,copy,yaml
from scripts import qd_ed_n36r3_admission as a
root=pathlib.Path.cwd(); base=root.parent/'autonomy_20261004'; out=base/'turns/001350'; review=base/'turns/001348/exact-b5-review'
def ref(p):
 b=p.read_bytes(); return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 tmp=p.with_suffix(p.suffix+'.tmp'); tmp.write_text(json.dumps(d,indent=2)+'\n'); os.replace(tmp,p)
def verify(r):
 assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']; return json.loads(pathlib.Path(r['path']).read_text())
report=json.loads((review/'report-v1.json').read_text()); assert ref(review/'report-v1.json')['sha256']=='cd4d78887dd8166df65c70e03189e2c5b2e1b48d581d56575d75796c255522ad'
plan=verify(report['plan']); verify(report['b5_review']); verify(report['checks_evidence']); verify(report['authority'])
assert not report['blocking_preparation_defects']; assert json.loads((review/'executor-exit-v1.json').read_text())['exit']==0
assert all(not pathlib.Path(f'/proc/{p}').exists() for p in [1076521,1076522])
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'
assert subprocess.check_output(['git','-C',plan['worktree'],'rev-parse','HEAD'],text=True).strip()=='bee9f6a4703e9d5d802d6b8c7950b69beefac4c0'
plan['b5_review']=report['b5_review']; a.independent_review(plan)
adoption={'schema':'n36r3-source-adoption-v1','approved':True,'owner_root':str(a.OWNER),'source_cwd':str(a.SOURCE),**{k:plan[k] for k in a.BINDINGS},'independent_review':plan['b5_review']}
write(out/'source-adoption-v1.json',adoption)
now=datetime.datetime.now(datetime.timezone.utc).isoformat(); next_action='Reconcile current owning state and all three journals under runner/state locks; create finite N36R3 accounting and authority using turn 001350 exact source-adoption-v1.json and accepted 001348 B5. Preserve unchanged 001347 draft/bindings. Then detached health review/release and fresh charged GPU7 readiness before distinct first-C0 release with mandatory G3 pause. No broad test repeats or source changes.'
old=json.loads((base/'turns/001349/operational-summary.json').read_text())
with (root/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for k in ['ledger_prefix','health_ledger_prefix','reservation_ledger_prefix']:
  r=old[k]; b=pathlib.Path(r['path']).read_bytes(); assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
 rec={'schema':'n36r3-exact-b5-terminal-reconciliation-v1','at':now,'decision':'ACCEPT_EXACT_B5_AND_ADOPT_SOURCE_RUNTIME_ONLY','report':ref(review/'report-v1.json'),'b5_review':report['b5_review'],'exit':ref(review/'executor-exit-v1.json'),'source_adoption':ref(out/'source-adoption-v1.json'),'reviewed_plan':report['plan'],'prior_handles_absent':[1076521,1076522],'ledger_prefixes':{k:old[k] for k in ['ledger_prefix','health_ledger_prefix','reservation_ledger_prefix']},'release_enabled':False,'target_met':False,'next_action':next_action}
 write(out/'terminal-reconciliation-v1.json',rec)
 for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
  d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text()); v=d['n36r3_exact_b5_review']; v.update(status='TERMINAL_EXACT_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED',live_handles=[],executor_exited=True,report=rec['report'],exit=rec['exit'],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'))
  d.update(n36r3_source_runtime_adoption=rec['source_adoption'],n36r3_exact_b5_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'),next_action=next_action,status='SOURCE_RUNTIME_ADOPTED_PENDING_ACCOUNTING_HEALTH',updated_at=now)
  if isinstance(d.get('active_executor'),dict) and d['active_executor'].get('output_directory')==str(review): d['active_executor']=None
  if is_yaml:
   temp=p.with_suffix('.yaml.tmp'); temp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True)); os.replace(temp,p)
  else: write(p,d)
 treepath=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json'; tree=json.loads(treepath.read_text()); node=tree['nodes']['15.6']; node.update(result='EXACT_B5_ACCEPTED_SOURCE_RUNTIME_ADOPTED_PENDING_RELEASE',insight='Independent exact B5 passed; root adopted unchanged source/runtime bindings. Accounting, fresh charged health, actual first-C0 G3 and all scientific gates remain open.',n36r3_exact_b5_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json')); write(treepath,tree)
summary={k:v for k,v in old.items() if k not in ['independent_review']}; summary.update(turn=1350,at=now,live_handles={},completed_work=['Verified bound authority, prior normal exit, current PID/boot/start identities and private ledger prefixes.','Reconciled successful terminal independent B5 review; verified exact hashes and actual B5 consumer acceptance.','Recorded exact source/runtime adoption and updated owning state/checkpoint/idea tree; no source edits, GPU dispatch or ledger charges.'],next_bounded_step=next_action,source_adoption=rec['source_adoption'],terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'),unresolved_evidence=['Locked finite accounting and fresh charged health/readiness release','First-C0 actual G3 lifecycle and continuation review','Original validation/formal/required ablation goal'])
write(out/'operational-summary.json',summary); (out/'operational-summary.sha256').write_text(ref(out/'operational-summary.json')['sha256']+'  operational-summary.json\n'); print(json.dumps({'decision':rec['decision'],'adoption':rec['source_adoption'],'next_action':next_action}))
