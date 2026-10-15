"""Independent root metadata review; no science imports or tensor decoding."""
import os,json,hashlib,math,resource,time
from pathlib import Path
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
resource.setrlimit(resource.RLIMIT_CPU,(60,60))
C=Path(__file__).resolve().parent; W=C.parents[2]/'study_worktree'
COHORT='N27_HYDRA_CONTINUATION_V1_20261001'; ARMS=('C0','Q0','N26','N27')
reads={}
def raw(p,cap=16*1024*1024):
 p=Path(p); assert p.suffix!='.pt' and p.stat().st_size<=cap,str(p)
 b=p.read_bytes(); assert len(b)<=cap; reads[str(p)]=len(b)
 assert sum(reads.values())<=512*1024*1024
 return b
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(raw(p))
def ref(p):return {'path':str(p),'sha256':sha(raw(p))}
def bound(q):
 b=raw(q['path']);assert sha(b)==q['sha256'],q['path'];return json.loads(b)
def alive(p):
 try:
  s=(Path('/proc')/str(p['pid'])/'stat').read_text();f=s[s.rfind(')')+2:].split()
  return f[0]!='Z' and f[19]==str(p['proc_start_ticks']) and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==p['boot_id']
 except FileNotFoundError:return False
r=read(C/'result-v1.json');plan=bound(r['plan']);seal=bound(r['prefix_seal'])
status=bound(r['terminal_status']);controller=read(C/'execution/controller-process-v1.json')
assert not alive(controller['process'])
assert r['source_commit']==plan['source_commit']=='e21d48ab33dbd3aca017349b6004c2ba7d981493'
assert (r['new_accepted_cells'],r['audited_cells'],r['new_dispatched'],r['dispatched'])==(13,16,13,17)
assert r['continuation_disposition']=='COMPLETE_THIRTEEN_VALID'
assert r['original_disposition']==bound(r['original_result'])['decision']=='INVALID_OR_INTERRUPTED'
assert r['validation_authorized'] is False and r['formal_authorized'] is False
assert r['controller_evidence']['consistent'] and status['status']=='completed_all_sixteen_audited'
assert [(v['task_id'],v['profile']) for v in r['accepted_cells']]==[(t,a) for t in range(4) for a in ARMS]
assert [v['episode_key'] for v in r['accepted_cells'][:3]]==[v['cell']['episode_key'] for v in seal['accepted_prefix']]
ledger=raw(W/'data/attempt-ledger.jsonl',32*1024*1024);assert ledger.endswith(b'\n')
events=[json.loads(x) for x in ledger.splitlines()]
local=[e for e in events if e.get('identity',{}).get('iteration')==COHORT]
assert local==bound(r['ledger_snapshot']) and len(local)==39
finals=[]
for i,row in enumerate(plan['episodes']):
 g=local[3*i:3*i+3];assert [e['event'] for e in g]==['reserved','dispatched','valid']
 assert len({e['attempt_id'] for e in g})==1 and all(e['episode_key']==row['episode_key'] for e in g)
 f=g[-1];assert f['outcome_valid'] is True and type(f['success']) is bool
 assert f['source_commit']==plan['source_commit'] and f['physical_gpu']==7
 assert f['identity']['task_id']==row['task_id'] and f['identity']['profile']==row['profile']
 assert f.get('retry_of')==row.get('retry_of')
 assert f['candidate_evaluations']==176*f['guided_chunks'] and f['score_batches']==11*f['guided_chunks']
 finals.append(f)
assert r['new_attempts']==[{'attempt_id':f['attempt_id'],'episode_key':f['episode_key'],'profile':f['identity']['profile'],'terminal':f} for f in finals]
for v in plan['code_files']:assert sha(raw(W/v['path']))==v['sha256'],v['path']
native={a:{} for a in ARMS};cells=[]
for item in seal['accepted_prefix']:native[item['cell']['profile']]=dict(item['native'])
for cell in r['accepted_cells']:
 receipt=bound(cell['worker_receipt']);ctx=bound(cell['worker_context']);audit=bound(cell['audit']);bound(cell['attempt_result'])
 assert receipt['accepted'] and receipt['main_exit_code']==0 and receipt['process_unchanged']
 assert audit['accepted'] and audit['evidence_complete'] and not audit['errors']
 assert receipt['attempt_id']==ctx['attempt_id']==cell['attempt_id']
 assert receipt['context']==cell['worker_context'] and receipt['audit_report']==cell['audit']
 assert receipt['source']==ctx['source'] and receipt['source']['commit']==cell['source_commit']
 assert receipt['plan']==ctx['plan']==(r['plan'] if cell['origin']=='new_continuation' else seal['original_plan'])
 assert receipt['main_argv_sha256']==sha(json.dumps(ctx['main_argv'],sort_keys=True,separators=(',',':')).encode())
 proc=read(Path(ctx['output_dir'])/'process.json')
 assert all(proc[k]==receipt['process'][k] for k in ('pid','proc_start_ticks','boot_id')) and not alive(proc)
 cu=receipt['worker_cuda'];assert cu['physical_gpu']==7 and cu['logical_device']=='cuda:0'
 assert cu['physical_uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187' and cu['identity_diagnostic']['status']=='matched'
 if cell['origin']=='new_continuation':
  assert receipt['source']['files']==plan['code_files']
  for k,v in receipt['n27_native_counts'].items():native[cell['profile']][k]=native[cell['profile']].get(k,0)+v
  m=receipt['n27_metrics']
  if m.get('present'):assert sha(raw(m['path'],64*1024*1024))==m['sha256']
 p=Path(ctx['output_dir'])/'eds_eval/stage_events.jsonl';b=raw(p);assert b.endswith(b'\n')
 stages=[json.loads(x) for x in b.splitlines()];queries=[x for x in stages if x.get('codex_logical_call_attempts',0)]
 assert all(x['transport']['backend']=='codex_cli' and x['transport']['auth_mode']=='chatgpt' for x in queries)
 calls=sum(x.get('codex_logical_call_attempts',0) for x in stages);failed=sum(x.get('codex_failed_calls',0) for x in stages)
 f=next(x['terminal'] for x in r['attempts'] if x['attempt_id']==cell['attempt_id'])
 assert calls==f['provider_logical_call_attempts']==f['provider_usage_complete_calls'] and failed==f['provider_failed_calls']==0
 assert f['provider_token_usage_complete'] and f['required_cost_telemetry_complete']
 assert f['guidance_api_request_attempts']==f['grounding_api_request_attempts']==0
 assert f['stage_api_request_attempts'] is None and f['provider_request_attempts'] is None
 cells.append({'profile':cell['profile'],'task_id':cell['task_id'],'origin':cell['origin'],'attempt_id':cell['attempt_id'],
 'success':cell['success'],'worker_receipt':cell['worker_receipt'],'stage_file':{'path':str(p),'sha256':sha(b)},'stage_logical_calls':calls,'stage_failed_calls':failed,'worker_exited':True})
assert native==r['native']
counts={a:{'audited':sum(x['profile']==a for x in cells),'success':sum(x['profile']==a and x['success'] for x in cells)} for a in ARMS}
assert counts==r['counts'];wins=counts['N27']['success']
promoted=wins>=2 and wins>counts['N26']['success'] and all(wins>=counts[a]['success'] for a in ARMS[:-1])
assert r['dev_gate_promoted']==promoted and r['decision']==('ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN')
for arm,fields in r['all_attempt_costs'].items():
 own=[x for x in r['attempts'] if x['profile']==arm]
 for k,slot in fields.items():
  values=[x['terminal'].get(k) for x in own];measured=[type(v) in (int,float) and math.isfinite(v) and v>=0 for v in values]
  assert math.isclose(sum(v for v,m in zip(values,measured) if m),slot['observed_total'],rel_tol=1e-12,abs_tol=1e-8)
  assert sum(measured)==slot['observed_attempts'] and [x['attempt_id'] for x,m in zip(own,measured) if not m]==slot['missing_attempts']
assert r['unknown_token_calls'] is None and r['all_attempt_token_usage_complete'] is False
old_invalid=seal['all_old_attempts'][-1]['attempt_id'];assert r['unmeasured_token_call_attempts']==[old_invalid]
review={'schema':'n27-hydra-root-terminal-review-v1','reviewed_unix':time.time(),'decision':'ACCEPT_TERMINAL_RECONSTRUCTION',
 'cohort_disposition':r['decision'],'result':ref(C/'result-v1.json'),'plan':r['plan'],'counts':counts,'cells':cells,
 'new_valid_cells':13,'imported_valid_cells':3,'all_dispatched_attempts':17,'original_invalid_retained':old_invalid,
 'episode_gpu_seconds':sum(x['terminal']['gpu_process_wall_seconds'] for x in r['attempts']),
 'new_episode_gpu_seconds':sum(f['gpu_process_wall_seconds'] for f in finals),
 'historical_backend_proof_separately_charged':seal['historical_backend_proof'],
 'stage_logical_calls_valid_cells':sum(x['stage_logical_calls'] for x in cells),'stage_failed_calls_valid_cells':sum(x['stage_failed_calls'] for x in cells),
 'provider':'codex_cli/chatgpt/current managed login only; no Poe or alternate fallback observed',
 'http_request_counts':'Unknown; logical CLI turns are not HTTP request counts.','invalid_attempt_tokens':'Unknown, not zero.',
 'source_files_verified':len(plan['code_files']),'native_receipt_counts':native,'controller_and_all_16_accepted_workers_exited':True,
 'protected_phases_closed':True,'target_status':'TARGET_NOT_MET','review_scope':'Recomputed metadata, identities, journal, outcomes, cost aggregates and provider routes. Checked original same-process CUDA audit receipts without replay.',
 'root_model_api_gpu_sim_calls':0,'root_tensor_payload_reads':0,'metadata_files_read':len(reads),'distinct_input_bytes':sum(reads.values())}
with (C/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:review[k] for k in ('decision','cohort_disposition','counts','stage_logical_calls_valid_cells','new_episode_gpu_seconds','episode_gpu_seconds','source_files_verified','target_status')}))
