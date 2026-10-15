"""CPU-only closure audit; no execution/acceptance changes, no raw provider text."""
from pathlib import Path
import collections,datetime,hashlib,json,statistics,subprocess,sys
W=Path('/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z')
A=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z')
sys.path.insert(0,str(W/'scripts'));import qd_ed_final_runner as r
plan=r.read_json(W/'data/qd-ed-n1w-approved-plan.json');events=r.read_events(W/'data/attempt-ledger.jsonl')
groups=[g for g in r.event_groups(events).values() if g[0]['identity']['iteration']=='N1W']
assert len(groups)==4 and all(g[-1]['event'] in r.TERMINAL for g in groups)
rows=[]
for g in groups:
 t=g[-1];out=Path(t['output_dir']);saved=r.read_json(out/'attempt-result.json');assert saved==t
 stage=r.read_events(out/'eds_eval/stage_events.jsonl');stage=[s for s in stage if s['query_status']!='skipped']
 phase=r.read_events(out/'eds_eval/phase_timing.jsonl');steps=[s['global_step'] for s in phase if s['name']=='adapter_step' and s['event']=='exit'];assert steps==list(range(len(steps)))
 metrics=r.read_events(out/'eds_eval/eds_metrics.jsonl');active=[m for m in metrics if m.get('qd_archive_active_for_chunk')]
 latency=[s['codex_call_latency_s'] for s in stage if s['query_status']=='ok']
 invariant_names=['nonfinite_count','qd_accounting_violation_count','qd_elite_monotonicity_violation_count','qd_final_selection_mismatch_count','qd_secondary_invariant_violation_count']
 row={'attempt_id':t['attempt_id'],'profile':t['identity']['profile'],'task_id':t['identity']['task_id'],'retry_of':t['retry_of'],'event':t['event'],'outcome_valid':t['outcome_valid'],'success':t['success'] if t['outcome_valid'] else None,'reason':t.get('reason'),'failure_detail':t.get('failure_detail'),'terminal_sha256':r.digest(out/'attempt-result.json'),'steps':len(steps),'last_phase':phase[-1],'gpu_process_wall_seconds':t['gpu_process_wall_seconds'],'stage_recorded_calls':len(stage),'stage_successful_calls':len(latency),'stage_failed_calls':sum(s['query_status']=='error' for s in stage),'successful_stage_latency_sum_s':sum(latency),'successful_stage_latency_median_s':statistics.median(latency) if latency else None,'successful_stage_latency_max_s':max(latency,default=None),'observed_stage_latency_including_failed_s':sum(s['codex_call_latency_s'] for s in stage),'accepted_fallback_calls':sum(bool(s['transport'].get('transport_fallback_notices')) and s['query_status']=='ok' for s in stage),'successful_calls_with_reconnect_diagnostics':sum(bool(s['transport'].get('error_diagnostics')) and s['query_status']=='ok' for s in stage),'known_completed_call_input_tokens':sum(s['codex_input_tokens'] for s in stage if s['query_status']=='ok'),'known_completed_call_output_tokens':sum(s['codex_output_tokens'] for s in stage if s['query_status']=='ok'),'all_episode_tokens_known':t.get('provider_token_usage_complete') is True,'recorded_guided_chunks':len(metrics),'active_qd_chunks':len(active),'candidate_counts':dict(collections.Counter(m['search_evaluation_count'] for m in metrics)),'score_batch_counts':dict(collections.Counter(m['score_call_count'] for m in metrics)),'invariant_totals':{k:sum(m[k] for m in metrics) for k in invariant_names},'qd_occupied_cells_range':[min((v for m in active for v in m['qd_occupied_cells_by_iter']),default=None),max((v for m in active for v in m['qd_occupied_cells_by_iter']),default=None)],'gpu_xid_records':r.read_json(out/'gpu-kernel-xid.json')['records'],'metrics_sha256':r.digest(out/'eds_eval/eds_metrics.jsonl'),'stage_sha256':r.digest(out/'eds_eval/stage_events.jsonl')}
 assert not row['gpu_xid_records'] and all(v==0 for v in row['invariant_totals'].values())
 assert all(m['search_evaluation_count']==176 and m['score_call_count']==11 for m in metrics)
 if row['profile']=='N1':
  assert all(m['qd_descriptor']=='target_distance_gripper_duty_v1' and m['qd_descriptor_axes']==[{'name':'target_distance','unit':'m'},{'name':'positive_gripper_command_duty','unit':'fraction'}] for m in active)
  ps=[b for m in active for b in m['qd_parent_descriptor_values_by_iter']]
  row.update(partial_trajectory_only=True,unique_proposed_duties=sorted({d[1] for m in active for b in m['shadow_qd_candidate_stream'] for d in b['descriptor_values']}),unique_sampled_parent_duties=sorted({d[1] for b in ps for d in b}),parent_batches=len(ps),parent_batches_with_multiple_duties=sum(len({d[1] for d in b})>1 for b in ps))
 rows.append(row)
assert len([r for r in rows if r['outcome_valid']])==2
budget=r.budget_snapshot(events,r.read_events(W/'data/gpu-healthcheck-ledger.jsonl'));assert budget['running']==0
migration=r.read_json(Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/resource-isolation-20260924-v1/migration.json'))
checks={}
for name in ('attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'):
 part=migration['partition_conservation'][name]['partitions']['X'];raw=(W/'data'/name).read_bytes();checks[name+'_original_partition_unchanged']=hashlib.sha256(raw[:part['bytes']]).hexdigest()==part['sha256']
checks['all_terminal_files_match_original_journal']=all(r.read_json(Path(g[-1]['output_dir'])/'attempt-result.json')==g[-1] for g in r.event_groups(events).values() if g[-1]['event'] in r.TERMINAL)
checks['frozen_source_files_unchanged']=all(r.digest(W/x['path'])==x['sha256'] for x in plan['code_files'])
checks['frozen_source_head_unchanged']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==plan['source_commit']
checks['original_plan_unchanged']=r.digest(W/'data/qd-ed-n1w-approved-plan.json')=='fa3408e75f49385178987db533b9d00d4fefb8f1dfa24647fd245cf9fe5980c2'
checks['runtime_unchanged']=r.digest(Path(plan['runtime_manifest_path']))==plan['runtime_manifest_sha256']
checks['no_inflight_attempts']=budget['running']==0
checks['protected_phases_unused']=budget['by_bucket']['validation']==budget['by_bucket']['formal']==0
checks['only_three_primary_one_recovery']=sum(not g[0]['retry_of'] for g in groups)==3 and sum(bool(g[0]['retry_of']) for g in groups)==1
checks['supervisor_exited']=not Path('/proc/3318782').exists()
checks['recovery_worker_exited']=not Path('/proc/3404890').exists()
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):checks['owner_runner_lease_released']=True
state=r.read_state(W/'research-state.yaml')
checks['state_budget_matches_ledger']=all(state['budget'][k]==budget[k] for k in ('dispatched','aborted','valid','invalid','completed','running','gpu_hours_consumed'))
checks['approved_caps_preserved']=state['budget']['max_episode_attempts']==250 and state['budget']['max_gpu_hours']==48 and state['budget']['reserved']==dict(zip(('baseline','development','validation','formal','recovery'),(13,125,60,40,12))) and state['budget']['gpu_hour_reservations']=={'validation':14.,'formal':10.}
checks['private_resources_active']=state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
assert all(checks.values()),checks
result={'schema':'n1w-final-audit-v1','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'decision':'INCOMPLETE_RECOVERY_EPISODE_TIMEOUT_NO_ADOPTION','target_met':False,'n1_effectiveness':'UNKNOWN_NO_VALID_EPISODE','planned_primary':30,'dispatched_primary':3,'undispatched_primary':27,'dispatched_recovery':1,'valid_scientific_cells':2,'n1_valid_scientific_cells':0,'phase_promotion_authorized':False,'total_n1w_gpu_hours':sum(x['gpu_process_wall_seconds'] for x in rows)/3600,'private_budget':budget,'available_nonprotected_gpu_hours':48-24-budget['gpu_hours_consumed'],'executed_source_commit':plan['source_commit'],'source_file_count':len(plan['code_files']),'plan_sha256':r.digest(W/'data/qd-ed-n1w-approved-plan.json'),'runtime_sha256':plan['runtime_manifest_sha256'],'rows':rows,'checks':checks,'limitations':['Completed event=valid is legacy accounting, not scientific validity; retain outcome_valid=false for the recovery.','N1 partial attempts are mechanism telemetry only; no task-success estimate, no pooling across versions.','Recovery has 22 completed recorded calls, but the process was killed during the next Stage phase: complete episode calls/tokens/compute remain unknown.','HTTPS fallback acceptance was not exercised in observed N1W events.','CLI/provider/network delay cause is unlocalized; no causal claim about GPU3 concurrency or N1 algorithm speed.']}
r.durable_json(A/'analysis/n1w/final-audit.json',result)
print(json.dumps(result,indent=2))
