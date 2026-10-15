"""Root terminal review: settled identities, hashes, scalar costs and independent gate.
Never launch/resume jobs or deserialize/replay episode tensors. Execute only after closure.
"""
from pathlib import Path
import collections,datetime,json,math,os,subprocess,sys,time
L=Path(__file__).resolve().parent;P=L.parent;W=P.parents[1]/'study_worktree'
os.environ['CUDA_VISIBLE_DEVICES']=''
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='2'
os.sched_setaffinity(0,{0,1});sys.dont_write_bytecode=True
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r,qd_ed_n23_worker as w
from scripts import qd_ed_n30_r2_contract as c,qd_ed_n30_r2_bridge as b
from scripts import qd_ed_n30_native as native
start=time.process_time();read=r.read_json;ref=c.ref
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def alive(record):
 try:
  fields=Path(f"/proc/{record['pid']}/stat").read_text().rsplit(')',1)[1].split()
  return fields[0]!='Z' and fields[19]==str(record['proc_start_ticks']) and record['boot_id']==boot
 except FileNotFoundError:return False
source=read(L/'source-manifest-execution-v1.json');plan=read(c.PLAN)
result=read(L/'result-v1.json');status=read(L/'execution/supervisor-status-v1.json')
assert source['commit']==plan['source_commit']=='6292fc8cffad2eec0f789e023d835ad3c1df146a'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==source['commit']
assert len(source['files'])==480 and source['files']==plan['code_files']
for f in source['files']:assert w.sha(W/f['path'])==f['sha256'],f['path']
for name in ('controller-process-v1.json','monitor-process-v1.json'):
 assert not alive(read(L/'execution'/name)),name
exit_record=read(L/'execution/root-launch-result-v1.json')
assert exit_record['controller']==ref(L/'execution/controller-process-v1.json')
assert result['plan']==ref(c.PLAN) and result['ledger_snapshot']==ref(L/'execution/terminal-ledger-v1.json')
assert result['source_commit']==source['commit'] and result['schema']=='n30-r2-combined-result-v1'
assert result['terminal_status']['content']==status
events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl')
h=c.history();b.current_subset(h,events)
all_local=[e for e in events if e.get('identity',{}).get('iteration') in {b.OLD,b.R1,c.COHORT}]
assert all_local==read(L/'execution/terminal-ledger-v1.json')
local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
groups=list(r.event_groups(local).values())
assert local==sum(groups,[]) and len(groups)<=10
assert [g[0]['episode_key'] for g in groups]==[row['episode_key'] for row in plan['episodes'][:len(groups)]]
accepted=[x['cell'] for x in h['imports']]
native_totals={arm:collections.Counter() for arm in c.ARMS}
for x in h['imports']:native_totals[x['cell']['profile']].update(x['native'])
reviews=[];invalid=[];new_cost=0.;dispatched=0;stage=collections.Counter()
for row,g in zip(plan['episodes'],groups):
 assert [x['event'] for x in g] in (['reserved','dispatched','valid'],['reserved','dispatched','aborted'],['reserved','aborted'])
 final=g[-1];aid=final['attempt_id'];out=Path(final['output_dir'])
 assert all(e['attempt_id']==aid and e['episode_key']==row['episode_key'] and e.get('retry_of')==row.get('retry_of')
  and e['identity']==r.episode_identity(row) and e['source_commit']==source['commit'] and e['plan_sha256']==ref(c.PLAN)['sha256'] for e in g)
 assert out.resolve().parent==(P/'artifacts/attempts').resolve() and read(out/'attempt-result.json')==final
 dispatched+=sum(e['event']=='dispatched' for e in g)
 seconds=final['gpu_process_wall_seconds'];assert type(seconds) in (int,float) and math.isfinite(seconds) and seconds>=0
 new_cost+=seconds
 proc_path=out/'process.json'
 if proc_path.exists():assert not alive(read(proc_path))
 rr={'attempt_id':aid,'episode_key':row['episode_key'],'profile':row['profile'],'task_id':row['task_id'],
  'outcome_valid':final.get('outcome_valid'),'success':final.get('success'),'gpu_process_wall_seconds':seconds,
  'attempt_result':ref(out/'attempt-result.json'),'process':ref(proc_path) if proc_path.exists() else None}
 # Actual transport records contain no API bodies in this review.
 calls=[x for x in r.read_events(out/'eds_eval/stage_events.jsonl') if x.get('query_status')!='skipped']
 for call in calls:
  transport=call['transport']
  assert (transport['backend'],transport['auth_mode'],transport['model'])==('codex_cli','chatgpt','gpt-6-astra')
  assert call.get('api_request_attempts') is None and call.get('api_sdk_retry_attempts') is None
 if type(final.get('provider_logical_call_attempts')) is int:
  assert len(calls)==final['provider_logical_call_attempts']
 for field in ('input_tokens','output_tokens','cached_input_tokens'):
  values=[x.get('codex_'+field) for x in calls]
  if all(type(v) is int for v in values) and type(final.get('provider_'+field)) is int:
   assert sum(values)==final['provider_'+field]
  if type(final.get('provider_'+field)) is int:stage[field]+=final['provider_'+field]
 stage['logical_calls_observed']+=len(calls)
 if type(final.get('provider_failed_calls')) is int:stage['failed_calls_observed']+=final['provider_failed_calls']
 rr['stage_records']=len(calls)
 if final.get('outcome_valid') is True:
  assert not invalid,'accepted cell after invalid forbidden'
  checked=c.accepted_cell(plan,row,events,W,vars(r));assert checked==final
  receipt=read(out/'eds_eval/in-worker-audit-receipt.json')
  report=w.read_ref(receipt['audit_report'])
  counts,aux=native.from_output(row['profile'],out,report,final['guided_chunks'])
  assert receipt['accepted'] and receipt['process_unchanged'] and receipt['main_exit_code']==0
  assert receipt['worker_cuda']['physical_gpu']==7 and receipt['worker_cuda']['physical_uuid']==c.GPU7_UUID
  assert receipt['n30_native_counts']==counts
  native_totals[row['profile']].update(counts)
  candidates=[x for x in result['accepted_cells'] if x['attempt_id']==aid];assert len(candidates)==1
  cell=candidates[0]
  assert all(cell[k]==v for k,v in {'episode_key':row['episode_key'],'original_episode_key':row['original_episode_key'],
   'profile':row['profile'],'task_id':row['task_id'],'source_commit':source['commit'],'success':final['success'],'inherited':False}.items())
  for key,name in (('audit','eds_eval/decision-evidence-audit.json'),('worker_context','n23-worker-context.json'),
   ('worker_receipt','eds_eval/in-worker-audit-receipt.json'),('attempt_result','attempt-result.json')):
   assert cell[key]==ref(out/name)
  accepted.append(cell);rr.update(native=counts,receipt=cell['worker_receipt'],audit=cell['audit'])
 else:
  invalid.append(aid)
  receiptpath=out/'eds_eval/in-worker-audit-receipt.json'
  rr['receipt']=ref(receiptpath) if receiptpath.exists() else None
 reviews.append(rr)
assert result['accepted_cells']==accepted and result['audited_cells']==len(accepted)
assert result['attempts']==[
 {'attempt_id':g[-1]['attempt_id'],'episode_key':g[-1]['episode_key'],'profile':g[-1]['identity']['profile'],'terminal':g[-1],'inherited_cost':i<4}
 for i,g in enumerate(b.group(h['events'])+groups)]
assert result['new_dispatched']==dispatched and result['all_dispatched']==4+dispatched
assert result['original_invalid_attempt']==b.ORIGINAL_FAILED and result['r1_invalid_attempt']==b.FAILED
counts={arm:{'audited':sum(x['profile']==arm for x in accepted),'success':sum(x['profile']==arm and x['success'] for x in accepted)} for arm in c.ARMS}
assert result['counts']==counts and result['native']=={arm:dict(v) for arm,v in native_totals.items()}
assert status['completed_keys']==[x['episode_key'] for x in accepted] and status['successes']=={a:v['success'] for a,v in counts.items()}
assert result['controller_evidence']['consistent'] is True
complete=len(accepted)==12;wins=counts['N30']['success'];remaining=4-counts['N30']['audited']
triples=all({x['profile'] for x in accepted if x['task_id']==task}==set(c.ARMS) for task in {x['task_id'] for x in accepted})
futile=triples and wins+remaining<3
substantive=all(native_totals['N30'].get(k,0)>0 for k in ('guided_decisions','parent_rounds_verified','active_insertions_verified'))
promoted=complete and not invalid and wins>=3 and wins>=max(counts[a]['success'] for a in ('C0','Q0')) and substantive
expected=('ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION' if promoted else
 'INVALID_OR_INTERRUPTED' if invalid else 'REJECT_NUMERIC_DEV_FUTILITY' if futile else 'REJECT' if complete else
 'RESOURCE_BUDGET_INCOMPLETE' if status['status']=='resource_budget_incomplete' else 'INVALID_OR_INTERRUPTED')
assert result['decision']==expected and result['dev_gate_promoted']==promoted
assert exit_record['exit_code']==(1 if status['status'] in {'failed','interrupted'} else 0)
assert result['validation_authorized'] is False and result['formal_authorized'] is False
prep=[e for e in resources if e.get('kind') in {'n30_resource_preparation_v1','n30_r1_resource_preparation_v1','n30_r2_resource_preparation_v1'} and e['event'] in {'completed','aborted'}]
prep_seconds=sum(e['gpu_process_wall_seconds'] for e in prep)
combined=h['old_seconds']+new_cost+prep_seconds
assert abs(c.local_seconds(events,resources,vars(r))-combined)<1e-8 and combined<=6*3600
snap=r.budget_snapshot(events,resources)
assert snap['running']==snap['gpu_healthcheck_inflight']==0 and snap['dispatched']==399+dispatched
assert abs(snap['gpu_hours_consumed']-(53.485552730447566+(new_cost+prep_seconds)/3600))<1e-8
review={'schema':'n30-r2-root-terminal-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'decision':expected,'source_commit':source['commit'],'source':ref(L/'source-manifest-execution-v1.json'),
 'source_files_rehashed':480,'plan':ref(c.PLAN),'result':ref(L/'result-v1.json'),
 'terminal_ledger':ref(L/'execution/terminal-ledger-v1.json'),'controller':ref(L/'execution/controller-process-v1.json'),
 'monitor':ref(L/'execution/monitor-process-v1.json'),'controller_exit':ref(L/'execution/root-launch-result-v1.json'),
 'controller_original_process_exited':True,'monitor_original_process_exited':True,'all_new_workers_original_process_exited':True,
 'new_dispatched':dispatched,'combined_dispatched':4+dispatched,'audited_cells':len(accepted),'counts':counts,
 'accepted_cells':accepted,'native':{a:dict(v) for a,v in native_totals.items()},'new_attempts':reviews,
 'new_invalid_attempts':invalid,'preserved_original_invalids':[b.ORIGINAL_FAILED,b.FAILED],
 'old_episode_gpu_seconds':h['old_seconds'],'new_episode_gpu_seconds':new_cost,'gpu_preparation_seconds':prep_seconds,
 'combined_gpu_hours':combined/3600,'budget_snapshot':snap,'new_stage':dict(stage),
 'http_requests':None,'http_retries':None,'matched_comparisons':result['matched_comparisons'],
 'independent_dev_gate':{'successes':wins,'remaining_unrun':remaining,'complete_matched_triples':triples,
  'maximum_possible_candidate_success':wins+remaining,'required_success':3,'substantive':substantive,'promoted':promoted},
 'root_tensor_deserializations':0,'root_numerical_replays':0,'new_evidence_hashes_verified':True,
 'original_controls_trust':h['historical_trust'],'history_bridge':ref(c.BRIDGE),
 'original_ledger_modified':False,'goal_status':'TARGET_NOT_MET','validation_authorized':False,'formal_authorized':False,
 'cpu_seconds':time.process_time()-start}
with (L/'root-terminal-review-v1.json').open('x') as f:json.dump(review,f,indent=2);f.write('\n')
print(json.dumps({k:review[k] for k in ('decision','counts','new_dispatched','combined_gpu_hours','new_stage','cpu_seconds')}))

