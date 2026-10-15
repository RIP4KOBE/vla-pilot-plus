import json,pathlib,hashlib,datetime,os,subprocess,sys,copy,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001362'
source=pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r3_generated_import_001299/implementation_worktree')
sys.path.insert(0,str(source))
from scripts import qd_ed_n36r3_admission as a, qd_ed_n36_contract as c, qd_ed_final_runner as r, qd_ed_n36_release as release
from scripts.qd_ed_n36r3_preparation import arithmetic
def ref(p):
 b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def readref(v):
 p=pathlib.Path(v['path']);assert ref(p)['sha256']==v['sha256'];return json.loads(p.read_text())
def write(p,d):
 tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2)+'\n');os.replace(tmp,p)
def live(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat'
 if not p.exists():return False
 v=p.read_text().rsplit(')',1)[1].split()
 return int(v[19])==h['start_ticks'] and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==h['boot_id'] and v[0]!='Z'
old=json.loads((base/'turns/001361/operational-summary-v1.json').read_text())
assert json.loads((base/'turns/001361/receipt.json').read_text())['exit']==0
driver=json.loads((base/'driver-status.json').read_text());assert driver['turn']==1362 and live(driver['driver']) and live(driver['process'])
assert not live({'pid':1155315,'start_ticks':148344868,'boot_id':driver['driver']['boot_id']})
for pid,ticks in [(1139735,148299249),(1139736,148299252)]:assert not live({'pid':pid,'start_ticks':ticks,'boot_id':driver['driver']['boot_id']})
assert ref(base/'user-authorization-v1.json')['sha256']=='a8d4dfc38b1fd5e9895d5a78b8eab0d0334ef5cb2716ba6aeeb35a8140c5506c'
assert ref(base/'completion-contract-v1.json')['sha256']=='4e825a595c3422824f5160b42690528a03a1ac4d8d2cf4025576a3bb59b2514c'
assert ref(base/'research-continuation-v1.md')['sha256']=='5cefad40c22cd57ac522344793c8ce734a51e9c09983d92f6ddd57dfd906710d'
review=json.loads((base/'turns/001358/exact-b5-review/report-v1.json').read_text());plan=readref(review['plan']);plan['b5_review']=review['b5_review'];a.independent_review(plan)
adoption=old['source_adoption'];readref(adoption)
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==old['candidate_source']
nextstep='Prepare detached N36R3 health review/release using turn 001362 adopted accounting/authority and 001358 exact B5 plan plus 001361 source adoption. Run fresh separately charged GPU7/provider readiness only after detached release consumer passes; then distinct first-C0 release and mandatory G3 pause. Preserve frozen 21fc93e source, BINDINGS and scientific gates; no broad test repeats.'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  c.stop.check(need=60)
  state=yaml.safe_load((root/'research-state.yaml').read_text());assert not state['current_owned_workers']
  anchors={};rows={}
  for v in old['ledger_prefixes'].values():
   p=pathlib.Path(v['path']);b=p.read_bytes();assert len(b)==v['bytes'] and ref(p)['sha256']==v['sha256'];anchors[p.name]=v;rows[p.name]=[json.loads(x) for x in b.splitlines() if x.strip()]
  snap=r.budget_snapshot(rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl']);assert snap['running']==snap['gpu_healthcheck_inflight']==0
  assert state['budget']['dispatched']==snap['dispatched'] and state['budget']['gpu_hours_consumed']==snap['gpu_hours_consumed']
  now=datetime.datetime.now(datetime.timezone.utc).isoformat()
  accounting={'schema':'n36r3-owning-accounting-v1','at':now,'cohort':c.DRAFT_N36R3_COHORT,'accounting':plan['accounting'],'source_adoption':adoption,'caps':c.CAPS,'limits':c.LIMITS,'healthchecks':a.HEALTH,'automatic_recoveries':0,'ledger_prefixes':anchors,'snapshot':snap,'arithmetic':arithmetic(snap),'approval_basis':ref(base/'user-authorization-v1.json'),'history_preserved':True,'release_enabled':False}
  write(out/'accounting-v1.json',accounting)
  authority={'schema':'n36-budget-authority-v1','approved':True,'cohort':c.DRAFT_N36R3_COHORT,'caps':c.CAPS,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,'starts_at':now,'weekly_window':{'ends_at':c.DEADLINE,'origin_gpu_hours':53.08404692669838,'increment_gpu_hours':168.0},'automatic_recoveries':0,'protocol':plan['protocol'],'accounting':plan['accounting'],'healthchecks':a.HEALTH,'source_adoption':adoption,'amendment':ref(out/'accounting-v1.json'),'ledger_prefixes':anchors,'approval_basis':ref(base/'user-authorization-v1.json')}
  a.validate_authority(plan,authority);write(out/'budget-authority-v1.json',authority);plan['authority']=ref(out/'budget-authority-v1.json')
  previous={'budget':copy.deepcopy(state['budget']),'n36_budget_authority':state.get('n36_budget_authority'),'source_adoption':state.get('n36r3_source_runtime_adoption')};write(out/'previous-budget-envelope-v1.json',previous)
  state['budget']['amendment']=authority['amendment'];state['budget']['previous_amendment_envelope']=ref(out/'previous-budget-envelope-v1.json');state['n36_budget_authority']=plan['authority'];state['n36r3_budget_authority']=plan['authority']
  release.validate_state(plan,authority,state);a.live_journals(plan,authority,rows['attempt-ledger.jsonl'],rows['gpu-healthcheck-ledger.jsonl'],rows['gpu-hour-reservation-ledger.jsonl'])
  rec={'schema':'n36r3-accounting-adoption-v1','at':now,'status':'PASS_ADOPTED_ACCOUNTING_PENDING_HEALTH_RELEASE','source':old['candidate_source'],'accounting':ref(out/'accounting-v1.json'),'authority':plan['authority'],'source_adoption':adoption,'reviewed_plan':review['plan'],'b5_review':review['b5_review'],'adopted_in_state':True,'release_enabled':False,'ledger_prefixes':anchors,'snapshot':snap,'historical_worktree_spelling_preserved':state['worktree'],'canonical_owner':state['canonical_worktree'],'alias_samefile':pathlib.Path(state['worktree']).samefile(root),'next_action':nextstep}
  write(out/'accounting-adoption-v1.json',rec)
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=state if isyaml else json.loads(p.read_text());d.update(n36r3_accounting_adoption=ref(out/'accounting-adoption-v1.json'),n36r3_budget_authority=plan['authority'],next_action=nextstep,status='ACCOUNTING_ADOPTED_PENDING_HEALTH_RELEASE',updated_at=now)
   if isyaml:
    tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(tmp,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';tree=json.loads(p.read_text());tree['nodes']['15.6'].update(n36r3_accounting_adoption=ref(out/'accounting-adoption-v1.json'),result='ACCOUNTING_ADOPTED_PENDING_HEALTH_RELEASE');write(p,tree)
summary={**old,'turn':1362,'at':now,'driver':driver,'accounting_adoption':ref(out/'accounting-adoption-v1.json'),'completed_work':['Verified actual driver/coordinator boot and start identities, prior normal exit and absent reviewer handles.','Reconciled three unchanged private journals under runner/state locks.','Adopted finite N36R3 accounting and authority with accepted source/B5; actual authority, state and live-journal consumers passed. Historical alias spelling and all charges preserved.'],'next_bounded_step':nextstep,'unresolved_evidence':['Detached health release and fresh charged readiness','Actual first-C0 G3 and continuation review','Original matched validation/formal/required ablations']}
write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'status':rec['status'],'arithmetic':accounting['arithmetic']['hours'],'summary':ref(out/'operational-summary-v1.json')}))
