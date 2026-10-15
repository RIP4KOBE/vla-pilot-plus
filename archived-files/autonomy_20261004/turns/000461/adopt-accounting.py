import sys,json,pathlib,hashlib,datetime,copy,yaml,subprocess
root=pathlib.Path.cwd(); sys.path.insert(0,str(root))
from scripts import qd_ed_final_runner as r, qd_ed_n23_worker as w, qd_ed_n32r3_contract as c
base=root.parent; turn=base/'autonomy_20261004/turns/000461'; out=base/'variants/n32_archive_eligible_capture/root-continuation-release-v3'
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,v):
 assert not p.exists(),str(p)
 w.atomic_json(p,v)
def prefix(p):
 b=p.read_bytes(); return dict(path=str(p),bytes=len(b),lines=len(b.splitlines()),sha256=hashlib.sha256(b).hexdigest())
assert not (base/'autonomy_20261004/STOP').exists()
assert now<'2026-10-10T17:42:00'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='36aac818c8ea0ec3ce18413e678963818bb5bb5d'
plan=json.loads((out/'composition-input-v1.json').read_text()); parent=c.read_ref(plan['parent_plan']); pa=c.read_ref(parent['authority'])
with r.locked(root/'data/qd-ed-state.lock'):
 statepath=root/'research-state.yaml'; cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json'; tp=cp.parent/'idea_tree.json'
 state=yaml.safe_load(statepath.read_text()); checkpoint=json.loads(cp.read_text()); tree=json.loads(tp.read_text())
 assert checkpoint['active_controller'] is None and not state['current_owned_workers']
 events=r.read_events(root/'data/attempt-ledger.jsonl'); resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
 snap=r.budget_snapshot(events,resources)
 assert snap['dispatched']==438 and snap['running']==0 and snap['gpu_healthcheck_inflight']==0
 assert all(g[-1]['event'] in r.TERMINAL for g in r.event_groups(events).values())
 assert snap['gpu_hours_consumed']==61.35722319715016
 ledgers={n:prefix(root/'data'/n) for n in ['attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl']}
 assert ledgers['attempt-ledger.jsonl']['sha256']=='8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6'
 ids=sorted({e['resource_id'] for e in resources if e.get('cohort')==c.COHORT or e.get('kind')=='n32r3_resource_preparation_v1'})
 assert ids==[], 'unexpected preparation must be reconciled'
 effective=min(pa['caps']['gpu_hours'],pa['weekly_window']['origin_gpu_hours']+pa['weekly_window']['increment_gpu_hours'])
 protected={k:max(0,h-snap['gpu_hours_by_bucket'][k]) for k,h in pa['caps']['protected_gpu_hours'].items()}
 arithmetic={'attempts_before':438,'new_attempts':16,'attempts_after_max':454,'new_by_bucket':{'baseline':5,'development':10,'recovery':1},'bucket_after_max':{k:snap['by_bucket'][k]+c.LIMITS.get(k,0) for k in pa['caps']['buckets']},'global_attempts_remaining_after':1346,'gpu_hours_before':snap['gpu_hours_consumed'],'new_gpu_hours_max':8.5,'gpu_hours_after_max':snap['gpu_hours_consumed']+8.5,'effective_ceiling':effective,'protected_remaining_gpu_hours':protected,'unprotected_gpu_hours_after_max':effective-snap['gpu_hours_consumed']-8.5-sum(protected.values()),'worker_seconds_max':16*1840,'cohort_seconds_max':30600,'additional_seconds_margin':30600-16*1840}
 assert arithmetic['unprotected_gpu_hours_after_max']>0
 assert all(arithmetic['bucket_after_max'][k]<=v for k,v in pa['caps']['buckets'].items())
 amendment={'schema':'n32r3-adopted-accounting-v1','approved':True,'parent_authority':parent['authority'],'limits':c.LIMITS,'ledger_prefixes':ledgers,'amendment':state['budget']['amendment'],'continuation_resource_ids':ids,'historical_charges_retained':True,'original_cohort_closed':True}
 write(out/'accounting-amendment-v1.json',amendment)
 authority={'schema':'n32r3-budget-authority-v1','approved':True,'cohort':c.COHORT,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':'2026-10-11T11:13:13Z','starts_at':now,'weekly_window':pa['weekly_window'],'caps':pa['caps'],'approval_basis':pa['approval_basis'],'amendment':state['budget']['amendment'],'ledger_prefixes':ledgers,'retained_history':snap,'arithmetic':arithmetic,'parent_authority':parent['authority'],'accounting_amendment':c.ref(out/'accounting-amendment-v1.json'),'preparation_review':plan['preparation_review'],'continuation_resource_ids':ids,'scope':'Finite operational continuation only; all 14 valid parent cells carried without replay; invalid task4 charge and unknown telemetry retained. No scientific promotion or GPU execution release.'}
 write(out/'budget-authority-v1.json',authority)
 protocol={'schema':'n32r3-production-protocol-v1','cohort':c.COHORT,'episodes':plan['episodes'],'limits':c.LIMITS,'worker_contract':c.WORKER_CONTRACT,'attempt_identity':'episode_key','deadline':c.DEADLINE,'promotion':c.PROMOTION,'futility':'complete_valid_triples_only','validation_authorized':False,'formal_authorized':False}
 write(out/'production-protocol-v1.json',protocol)
 draft={**plan,'authority':c.ref(out/'budget-authority-v1.json'),'accounting_amendment':c.ref(out/'accounting-amendment-v1.json'),'protocol':c.ref(out/'production-protocol-v1.json'),'expected_manifests':json.loads((pathlib.Path(plan['artifact_root'])/'manifests-v1/manifest-index.json').read_text())['expected_manifests']}
 write(out/'accounted-composition-input-v1.json',draft)
 review={'schema':'n32r3-accounting-adoption-v1','at':now,'authority':draft['authority'],'protocol':draft['protocol'],'composition_input':c.ref(out/'accounted-composition-input-v1.json'),'arithmetic':arithmetic,'ledger_prefixes':ledgers,'gpu_dispatched':False,'production_release_approved':False}
 write(turn/'accounting-adoption.json',review)
 for p in [statepath,cp,tp]: (turn/('pre-accounting-'+p.name)).write_bytes(p.read_bytes())
 next_action='N32R3 finite accounting/protocol adopted; use root-continuation-release-v3/accounted-composition-input-v1.json. Verify frozen runtime and fresh official Stage image transport, obtain independent detached production review, validate release and current GPU7 admission before dispatch. No replay of 14 valid cells; invalid task4 remains charged.'
 state['n32r3_budget_authority']=draft['authority']; state['n32r3_accounting_adoption']=c.ref(turn/'accounting-adoption.json'); state['next_action']=next_action; state['updated_at']=now
 checkpoint['n32r3_accounting_adoption']=c.ref(turn/'accounting-adoption.json'); checkpoint['next_action']=next_action; checkpoint['updated_at']=now
 tree['nodes']['15.2']['n32r3_accounting_adoption']=c.ref(turn/'accounting-adoption.json')
 temp=statepath.with_suffix('.yaml.tmp'); temp.write_text(yaml.safe_dump(state,sort_keys=False,allow_unicode=True)); temp.replace(statepath)
 w.atomic_json(cp,checkpoint); w.atomic_json(tp,tree)
 write(turn/'state-reconciliation.json',{'state':c.ref(statepath),'checkpoint':c.ref(cp),'tree':c.ref(tp),'ledger_unchanged':all(prefix(pathlib.Path(v['path']))==v for v in ledgers.values()),'gpu_dispatched':False})
print(json.dumps(review,indent=2))
