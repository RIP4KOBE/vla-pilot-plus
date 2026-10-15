import json,pathlib,hashlib,datetime,yaml,sys
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_n34_contract as c
out=(root.parent/'variants/n34_observed_jaw_approach/root-production-release-v1').resolve();out.mkdir(exist_ok=False)
t=root.parent/'autonomy_20261004/turns/000568'; prior=root.parent/'autonomy_20261004/turns/000567'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(n,v):
 p=out/n;p.write_text(json.dumps(v,indent=2)+'\n');return ref(p)
s=yaml.safe_load((root/'research-state.yaml').read_text());budget=s['budget'];review=json.loads((root.parent/'autonomy_20261004/turns/000563/n34-prospective-accounting-review-v1.json').read_text());entry=json.loads((t/'entry-reconciliation-v1.json').read_text())
assert not pathlib.Path(c.stop_path(root)).exists();assert s['active_controller'] is None
for n,e in entry['ledger_prefixes'].items():
 b=(root/'data'/n).read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256']
plan=json.loads((prior/'prospective-draft-v1/plan.draft.json').read_text());c.validate_draft(plan)
events=[json.loads(x) for x in (root/'data/attempt-ledger.jsonl').read_text().splitlines()];assert not {r['episode_key'] for r in plan['episodes']} & {e.get('attempt_id') for e in events}
authority={'schema':'n34-budget-authority-v1','approved':True,'cohort':c.COHORT,'limits':c.LIMITS,'validation_authorized':False,'formal_authorized':False,'coordinator_ends_at':c.DEADLINE,'starts_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'caps':{'attempts':budget['max_episode_attempts'],'gpu_hours':budget['max_gpu_hours'],'buckets':budget['reserved'],'protected_gpu_hours':budget['gpu_hour_reservations']},'approval_basis':ref(root.parent/'autonomy_20261004/user-authorization-v1.json'),'amendment':budget['amendment'],'weekly_window':{**review['retained_weekly_origin'],'ends_at':c.DEADLINE},'prior_weekly_window':review['retained_weekly_origin'],'accounting_review':ref(root.parent/'autonomy_20261004/turns/000563/n34-prospective-accounting-review-v1.json'),'ledger_prefixes':entry['ledger_prefixes'],'history_snapshot':review['snapshot'],'arithmetic':{k:review[k] for k in ['remaining_attempts','remaining_by_bucket','protected_gpu_hours_remaining','private_gpu_hours_remaining','effective_gpu_cap','effective_unprotected_gpu_hours_remaining','n34_max_additional','after_max_n34']},'window_amendment_scope':'N34 only through October11 under standing seven-day authorization. Prior N31 October10 freeze remains unchanged. Original53.08404692669838GPUh origin and168GPUh increment retained; effective cap min(224,53.08404692669838+168)=221.08404692669836. No spent cost reset, cap increase, reserve borrowing, or automatic recovery.'}
aref=write('budget-authority-v1.json',authority)
protocol={'schema':'n34-production-protocol-v1','cohort':c.COHORT,'episodes':plan['episodes'],'limits':c.LIMITS,'worker_contract':c.WORKER_CONTRACT,'attempt_identity':'episode_key','deadline':c.DEADLINE,'promotion':{'all_valid_cells':30,'n34_min_successes':5,'at_least_both_controls':True,'matched_controls_required':True},'futility':'complete_valid_triples_only','validation_authorized':False,'formal_authorized':False}
pref=write('protocol.frozen-v1.json',protocol)
plan.update(schema='n34-released-plan-v1',frozen=True,release_enabled=True,authority=aref,protocol=pref,attempt_identity='episode_key',phase_authorization={'dev':True,'validation':False,'formal':False});del plan['root_review'];del plan['execution_release']
planref=write('plan.frozen-v1.json',plan)
base={'schema':'n34-execution-release-v1','approved':True,'plan':planref,'authority':aref,'protocol':pref,'source':plan['source'],'scientific_source':plan['scientific_source'],'runtime_closure':plan['runtime_closure'],'controller_semantics':plan['controller_semantics'],'runtime':plan['runtime'],'limits':c.LIMITS,'phase_authorization':plan['phase_authorization']}
rr=write('root-production-review-v1.json',{**base,'schema':'n34-root-production-review-v1','decision':'APPROVED'})
release=write('execution-release-v1.json',{**base,'root_review':rr})
record={'schema':'n34-detached-release-preparation-v1','plan':planref,'release':release,'authority':aref,'runtime_review':ref(prior/'n34-runtime-regeneration-review-v1.json'),'boundary_review':ref(root.parent/'autonomy_20261004/turns/000566/n34-release-boundary-root-review-v1.json'),'full_public_validation':'PENDING','adopted':False,'gpu_dispatched':False,'target_met':False}
(t/'release-preparation-v1.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['plan','release','full_public_validation']}))
