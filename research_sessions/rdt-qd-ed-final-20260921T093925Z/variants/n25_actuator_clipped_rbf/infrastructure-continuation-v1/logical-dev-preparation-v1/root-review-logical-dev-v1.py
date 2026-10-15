import json,hashlib,subprocess,sys
from pathlib import Path
P=Path(__file__).resolve().parent;C=P.parent;R=C.parent.parent.parent;W=R/'study_worktree'
sys.path[:0]=[str(W/'scripts'),str(W)]
from scripts import qd_ed_final_runner as r
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def get(p):return json.loads(Path(p).read_text())
ev=get(C/'logical-dev-evidence-v1.json'); result=get(C/'result-v1.json'); root=get(C/'root-terminal-review-v1.json')
assert ev['logical_disposition']==root['cohort_disposition']==result['decision']=='REJECT_NUMERIC_FUTILITY'
assert ev['counts']==root['counts']==result['counts']
assert ev['allow_n26'] is ev['allow_validation'] is ev['gpu_authorized'] is False
assert ev['accepted_cells']==28 and ev['accepted_mapping']==result['accepted_cells']
assert len(ev['attempt_ids'])==len(set(ev['attempt_ids']))==29
for arm in ('C0','Q0','N23','N25'):
 cells=[x for x in ev['accepted_mapping'] if x['profile']==arm]
 assert len(cells)==7 and sum(x['success'] for x in cells)==ev['counts'][arm]['success']
assert ev['counts']['N25']['success']+3<5
assert ev['historical_unknowns']['unknown_token_calls']==6 and ev['original_disposition']=='INVALID_OR_INTERRUPTED'
for label,attempts in [('old',result['attempts'][:19]),('new',result['attempts'][19:]),('combined',result['attempts'])]:
 cost=ev['cost_coverage'][label];total_unknown=0
 for item in attempts:total_unknown+=item['terminal']['provider_logical_call_attempts']-item['terminal']['provider_usage_complete_calls']
 assert cost['unknown_token_calls']==total_unknown==(0 if label=='new' else 6)
 for arm,fields in cost['all_attempt_costs'].items():
  rows=[x for x in attempts if x['profile']==arm]
  for field,entry in fields.items():
   vals=[x['terminal'].get(field) for x in rows]; valid=[x for x in vals if type(x) in (int,float)]
   assert sum(valid)==entry['observed_total'] and len(valid)==entry['observed_attempts']
   assert entry['missing_attempts']==[x['attempt_id'] for x in rows if type(x['terminal'].get(field)) not in (int,float)]
assert sum(x['terminal']['provider_logical_call_attempts'] for x in result['new_attempts'])==210
assert all(x['terminal']['provider_failed_calls']==0 for x in result['new_attempts'])
assert ev['reader']==ref(W/'scripts/qd_ed_n25_cont_downstream.py')
assert ev['provenance']['root_review']==ref(C/'root-terminal-review-v1.json')
data=get(ev['input']['path']);assert sha(ev['input']['path'])==ev['input']['sha256']
for q in data['files']:assert sha(q['path'])==q['sha256']
old_unknowns=ev['historical_unknowns']
h=R/'variants/n26_clean_output_rbf/conditional-controller-cpu-v1'
assert sha(h/'root-cpu-review-v1.json')=='1c7246994b2ce98c3c909484dfa24eb966c6cd1390d46cd4707d3566563c8f8b'
with r.locked(C/'execution/supervisor.lock',nonblocking=True):
 with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
  events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
  snap=r.budget_snapshot(events,resources)
  assert snap['running']==snap['gpu_healthcheck_inflight']==0
  d={'schema':'n25-root-logical-dev-evidence-review-v1','accepted':True,'evidence':ref(C/'logical-dev-evidence-v1.json'),
    'input':ev['input'],'terminal_review':ev['provenance']['root_review'],
    'counts':ev['counts'],'accepted_cells':28,'attempts_including_original_invalid':29,
    'new_stage_calls_complete':210,'new_stage_failed_calls':0,'historical_unknowns':old_unknowns,
    'original_disposition':'INVALID_OR_INTERRUPTED','logical_disposition':'REJECT_NUMERIC_FUTILITY',
    'costs_independently_recomputed':True,'metadata_inventory_reverified':206,
    'tensor_reads':0,'gpu_authorized':False,'validation_authorized':False,
    'n26_predecessor_and_source_integration_authorized':True,
    'next_source':'6026794cd5d52f3a5054bf2704ebb3c516f9f47e',
    'accepted_n26_cpu_review':ref(h/'root-cpu-review-v1.json'),
    'budget_snapshot':snap,'reviewer':ref(__file__)}
  with (C/'root-logical-dev-review-v1.json').open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
  print(json.dumps({'review':ref(C/'root-logical-dev-review-v1.json'),'budget_snapshot':snap}))

