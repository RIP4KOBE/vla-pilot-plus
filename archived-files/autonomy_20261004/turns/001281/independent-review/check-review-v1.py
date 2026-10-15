import os,sys,json,hashlib,subprocess,time,datetime as dt
from pathlib import Path
from decimal import Decimal,localcontext
started=time.monotonic()
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
root=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36r2_alias_recovery_001250/implementation_worktree')
out=Path(__file__).parent
sys.path.insert(0,str(root))
from scripts import qd_ed_n36r2_admission as gate,qd_ed_n36_contract as c,qd_ed_n36_release as release,qd_ed_n36_stop as stop,qd_ed_n23_worker as w,qd_ed_final_runner as r
A=json.loads((out/'authority-v1.json').read_text()); prep=Path(A['preparation_report']['path']).parent
result={'schema':'n36r2-independent-cpu-checks-v1','bindings':[],'checks':{},'negative_checks':[]}
def bind(ref):
 p=Path(ref['path']);data=p.read_bytes();actual={'path':str(p),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 assert actual['sha256']==ref['sha256'] and ('bytes' not in ref or ref['bytes']==len(data)),str(p)
 result['bindings'].append(actual);return data
def reject(label,fn):
 try:fn()
 except (ValueError,KeyError,TypeError,OSError) as e:result['negative_checks'].append({'case':label,'exception':type(e).__name__,'reason':str(e)})
 else:raise AssertionError('FAIL OPEN '+label)
for key in ['standing_authority','root_acceptance','preparation_report']:bind(A[key])
report=json.loads((prep/'report-v1.json').read_text())
for key in ['authority','evidence_index','markdown','accounting','routing','source_changes','rebindings','owner_state_drift','findings']:bind(report[key])
index=json.loads((prep/'evidence-index-v1.json').read_text())
# Only package evidence, no executor logs or recursive historical provenance.
for ref in index['artifacts']:
 n=Path(ref['path']).name
 if n.startswith('context.') or n in ['current-ledger-snapshot-v1.json','focused-tests-final.json','focused-tests-final.log','package-boundary-checks-v1.json','check-package-v1.py','plan.unbound-disabled-v1.json','accounting.prospective-disabled-v1.json','protocol.prospective-disabled-v1.json','preparation-checks-v1.json','source-diff.patch']:bind(ref)
changes=json.loads((prep/'source-change-manifest-v1.json').read_text())
for entry in changes['files']:
 data=bind(entry['current']); rel=entry['relative_path']
 assert data==subprocess.check_output(['git','show',A['base_source']+':'+rel],cwd=root)
 if entry['before_sha256']:
  assert hashlib.sha256(subprocess.check_output(['git','show',changes['base_commit']+':'+rel],cwd=root)).hexdigest()==entry['before_sha256']
actual_diff=subprocess.check_output(['git','diff',changes['base_commit'],A['base_source'],'--'],cwd=root)
result['source_diff']={'bytes':len(actual_diff),'sha256':hashlib.sha256(actual_diff).hexdigest()}
result['source_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
result['owner_head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=A['owner'],text=True).strip()
assert result['source_head']==A['base_source'] and result['owner_head']=='ca4e6a96d049c7ebb1f302d755883388ddbfdbd8'
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=root,text=True)
snapshot=json.loads((prep/'current-ledger-snapshot-v1.json').read_text())
ledgers={}
for name,ref in snapshot['ledger_prefixes'].items():
 data=bind(ref);ledgers[name]=[json.loads(line) for line in data.splitlines() if line.strip()]
events=ledgers['attempt-ledger.jsonl'];resources=ledgers['gpu-healthcheck-ledger.jsonl']
# Project accounting-only fields before running arithmetic; never inspect outcome content.
keep={'attempt_id','episode_key','event','budget_bucket','gpu_process_wall_seconds','outcome_valid','resource_id'}
events=[{k:v for k,v in e.items() if k in keep} for e in events]
resources=[{k:v for k,v in e.items() if k in keep} for e in resources]
live=r.budget_snapshot(events,resources);assert live==snapshot['snapshot']
assert live['dispatched']==504 and live['gpu_hours_consumed']==75.49265038509455
gate.preserve_charges(events)
groups=r.event_groups(events);assert all(g[-1]['event'] in r.TERMINAL for g in groups.values())
health={}
for e in resources:health.setdefault(e['resource_id'],[]).append(e)
assert all(g[-1]['event'] in {'completed','aborted'} for g in health.values())
with localcontext() as ctx:
 ctx.prec=65
 seconds=sum((Decimal(str(g[-1]['gpu_process_wall_seconds'])) for g in groups.values()),Decimal(0))+sum((Decimal(str(g[-1]['gpu_process_wall_seconds'])) for g in health.values()),Decimal(0))
 hours=seconds/3600
calc=json.loads((prep/'accounting-calculation-v1.json').read_text())
assert seconds==Decimal(calc['arithmetic']['terminal_decimal_seconds']) and hours==Decimal(calc['arithmetic']['terminal_decimal_hours'])
plan=json.loads((prep/'plan.unbound-disabled-v1.json').read_text())
c.validate_draft(plan);gate.validate_protocol(plan)
assert plan['episodes']==c.plan_rows(plan)
assert plan['authority'] is None and plan['b5_review'] is None and plan['release_enabled'] is False
assert len(plan['episodes'])==40
ids={row['episode_key'] for row in plan['episodes']};assert len(ids)==40 and not ids.intersection(groups)
assert not set(calc['fresh_healthcheck_ids']).intersection(health)
for ref in plan['expected_manifests'].values():
 manifest=json.loads(bind(ref));assert not os.path.lexists(manifest['output_dir'])
reject('disabled exact package release',lambda:release.validate_release(c.ref(prep/'plan.unbound-disabled-v1.json'),None))
reject('missing independent review',lambda:gate.independent_review(plan))
reject('pure allowance cannot substitute detached release',lambda:c.pre_dispatch(plan['episodes'][0],{},now=dt.datetime.now(dt.timezone.utc),stop_path=stop.STOP_PATHS[0],cohort=c.DRAFT_RECOVERY_COHORT))
statepath=Path(A['owner'])/'research-state.yaml';statebytes=statepath.read_bytes();state=r.read_state(statepath)
result['owner_state']={'path':str(statepath),'sha256':hashlib.sha256(statebytes).hexdigest(),'bytes':len(statebytes),'budget_unchanged_since_preparation':state['budget']==snapshot['budget'],'n36_budget_authority':state.get('n36_budget_authority')}
assert state['budget']==snapshot['budget']
stop.check(need=1900)
result['STOP_paths']={p:os.path.lexists(p) for p in stop.STOP_PATHS}
result['accounting']={'attempts':504,'gpu_hours':live['gpu_hours_consumed'],'decimal_terminal_seconds':str(seconds),'decimal_terminal_hours':str(hours),'arithmetic':calc['arithmetic'],'attempt_arithmetic':calc['attempts'],'bucket_arithmetic':calc['bucket_arithmetic'],'unsettled_episode_groups':0,'unsettled_healthchecks':0,'retained_invalid_charges':gate.draft.PRESERVED}
result['checks']={'source_matches_commit':True,'owner_source_unadopted':True,'tracked_worktree_clean':True,'all_three_ledgers_exact_unchanged':True,'live_accounting_matches_preparation':True,'exact_decimal_terminal_sum':True,'protocol_and_calculation_valid':True,'forty_ids_fresh':True,'forty_outputs_absent':True,'forty_one_healthcheck_ids_fresh':True,'both_STOP_aliases_absent':True}
result['reuse']={'focused_tests_passed':11,'package_negative_cases':52,'rerun':False,'scope':'Retained hash-verified CPU evidence only; no current worker/provider/device evidence'}
result['at']=dt.datetime.now(dt.timezone.utc).isoformat();result['wall_seconds']=time.monotonic()-started;result['cpu_affinity']=sorted(os.sched_getaffinity(0));result['test_timeout_seconds']=120
(out/'check-results-v1.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print(json.dumps({k:result[k] for k in ['checks','negative_checks','wall_seconds','owner_state']},indent=2))
