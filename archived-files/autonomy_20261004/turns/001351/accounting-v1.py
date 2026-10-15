import json,pathlib,hashlib,datetime,os,subprocess,yaml
from scripts import qd_ed_n36r3_admission as a, qd_ed_n36_contract as c, qd_ed_final_runner as r
from scripts.qd_ed_n36r3_preparation import arithmetic
root=pathlib.Path.cwd(); base=root.parent/'autonomy_20261004'; out=base/'turns/001351'
def ref(p):
 b=p.read_bytes(); return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 temp=p.with_suffix('.tmp'); temp.write_text(json.dumps(d,indent=2)+'\n'); os.replace(temp,p)
def readref(v):
 p=pathlib.Path(v['path']); assert ref(p)['sha256']==v['sha256']; return json.loads(p.read_text())
old=json.loads((base/'turns/001350/operational-summary.json').read_text())
plan=json.loads((base/'turns/001347/manifest-refresh/plan.draft.json').read_text()); review=json.loads((base/'turns/001348/exact-b5-review/report-v1.json').read_text()); plan['b5_review']=review['b5_review']; a.independent_review(plan)
adoption=ref(base/'turns/001350/source-adoption-v1.json'); assert adoption==old['source_adoption']; readref(adoption)
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==old['source']
with r.locked(root/'data/qd-ed-runner.lock', nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=60)
  state=yaml.safe_load((root/'research-state.yaml').read_text()); anchors={}; rows={}
  for key in ['ledger_prefix','health_ledger_prefix','reservation_ledger_prefix']:
   v=old[key]; p=pathlib.Path(v['path']); b=p.read_bytes(); assert len(b)==v['bytes'] and ref(p)['sha256']==v['sha256']; anchors[p.name]=v; rows[p.name]=[json.loads(line) for line in b.splitlines() if line.strip()]
  snap=r.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']); assert snap['running']==snap['gpu_healthcheck_inflight']==0
  assert state['budget']['dispatched']==snap['dispatched'] and state['budget']['gpu_hours_consumed']==snap['gpu_hours_consumed']
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  accounting={'schema':'n36r3-owning-accounting-v1','at':now,'cohort':c.DRAFT_N36R3_COHORT,'accounting':plan['accounting'],'source_adoption':adoption,'caps':c.CAPS,'limits':c.LIMITS,'healthchecks':a.HEALTH,'automatic_recoveries':0,'ledger_prefixes':anchors,'snapshot':snap,'arithmetic':arithmetic(snap),'approval_basis':ref(base/'user-authorization-v1.json'),'history_preserved':True,'release_enabled':False}
  write(out/'accounting-v1.json',accounting)
  authority={'schema':'n36-budget-authority-v1','approved':True,'cohort':c.DRAFT_N36R3_COHORT,'caps':c.CAPS,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,'starts_at':now,'weekly_window':{'ends_at':c.DEADLINE,'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.0},'automatic_recoveries':0,'protocol':plan['protocol'],'accounting':plan['accounting'],'healthchecks':a.HEALTH,'source_adoption':adoption,'amendment':ref(out/'accounting-v1.json'),'ledger_prefixes':anchors,'approval_basis':ref(base/'user-authorization-v1.json')}
  a.validate_authority(plan,authority)
  write(out/'budget-authority-v1.json',authority)
  nextstep='Adopt turn 001351 finite accounting/authority under owner locks after resolving lexical worktree admission: state retains historical worktree spelling while validate_state requires canonical OWNER. Preserve lexical ownership policy; document alias identity, do not silently rewrite it. Then prepare detached health review/release with accepted exact B5 and unchanged BINDINGS; fresh charged GPU7 health precedes first-C0 and mandatory G3 pause. No scientific change or broad test repeat.'
  rec={'schema':'n36r3-accounting-reconciliation-v1','at':now,'status':'PASS_FINITE_ACCOUNTING_AUTHORITY_CONSUMER','source':old['source'],'accounting':ref(out/'accounting-v1.json'),'authority':ref(out/'budget-authority-v1.json'),'adopted_in_state':False,'release_enabled':False,'state_worktree':state['worktree'],'required_owner':str(a.OWNER),'lexical_admission_mismatch':state['worktree']!=str(a.OWNER),'next_action':nextstep}
  write(out/'accounting-reconciliation-v1.json',rec)
  for p,is_yaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if is_yaml else json.loads(p.read_text()); d.update(n36r3_finite_accounting_preparation=ref(out/'accounting-reconciliation-v1.json'),next_action=nextstep,updated_at=now)
   if is_yaml:
    temp=p.with_suffix('.tmp'); temp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True)); os.replace(temp,p)
   else: write(p,d)
summary={**old,'turn':1351,'at':now,'live_handles':{},'completed_work':['Verified bound handoff/authority, driver PID/boot/start identity, normal prior exit and unchanged private ledger prefixes.','Reconciled finite 40-cell/21-GPU-hour accounting under runner/state locks; existing admission consumer accepted new exact accounting and authority.','Preserved source, all charges and reserves; recorded lexical state admission mismatch before resource adoption.'],'next_bounded_step':nextstep,'accounting_reconciliation':ref(out/'accounting-reconciliation-v1.json'),'unresolved_evidence':['Lexical owner-state admission mismatch before authority adoption','Detached health/release and fresh charged readiness','First-C0 G3 and original validation/formal/ablation evidence']}
write(out/'operational-summary.json',summary); (out/'operational-summary.sha256').write_text(ref(out/'operational-summary.json')['sha256']+'  operational-summary.json\n'); print(json.dumps(rec)); print(json.dumps(accounting['arithmetic']['hours']))
