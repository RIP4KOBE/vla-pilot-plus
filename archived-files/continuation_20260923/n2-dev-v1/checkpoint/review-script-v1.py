from pathlib import Path
import collections, hashlib, importlib.util, json, math, subprocess
import torch

W=Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
A=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')
HEAD='525506ca3198f54d86dadf84bbb76eb64926d87a'
OUT=A/'continuation_20260923/n2-dev-v1/checkpoint'
assert not torch.cuda.is_initialized()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==HEAD
hashes={}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
 hashes[str(path)]=sha(path)
 return json.loads(path.read_text())
def lines(path):
 hashes[str(path)]=sha(path)
 return [json.loads(x) for x in path.read_text().splitlines() if x]
def finite(x): return isinstance(x,torch.Tensor) and bool(torch.isfinite(x).all())
def native_key(t):
 assert finite(t)
 return (str(t.dtype),tuple(t.shape),hashlib.sha256(t.contiguous().view(torch.uint8).numpy().tobytes()).hexdigest())
def fp(t): return hashlib.sha256(t.float().contiguous().numpy().astype('<f4',copy=False).tobytes()).hexdigest()
violations={k:[] for k in ('finite_action','source_compute','raw_stage_separation','substantive_qd_activation')}
def check(gate,ok,reason):
 if not ok: violations[gate].append(reason)

sources=['core/qd_executed_quality.py','core/rdt_policy_steer.py','core/qd_ed.py','core/eds_eval_metrics.py','core/decision_evidence.py','main.py','scripts/audit_decision_evidence.py','scripts/qd_ed_final_runner.py','tests/test_rdt_steer.py','results/6.1-executed-prefix-quality/cpu-validation.json']
for rel in sources:
 path=W/rel;hashes[str(path)]=sha(path)
 frozen=subprocess.check_output(['git','show',HEAD+':'+rel],cwd=W)
 check('source_compute',hashlib.sha256(frozen).hexdigest()==hashes[str(path)],'reviewed_source_modified:'+rel)
summary=[]; data={}
zero_fields=('nonfinite_count','gripper_qpos_violation_count','qd_accounting_violation_count','qd_elite_monotonicity_violation_count','qd_final_selection_mismatch_count','qd_secondary_invariant_violation_count')
for arm,suffix in [('C0','3cc1e46f83d0'),('Q0','28dd3c7a9e74'),('N2','45c5f8694f85')]:
 paths=list((A/'attempts').glob('*__'+suffix));assert len(paths)==1
 path=paths[0];result=read(path/'attempt-result.json');comps=lines(path/'eds_eval/episode_compute.jsonl');assert len(comps)==1
 comp=comps[0];metrics=lines(path/'eds_eval/eds_metrics.jsonl');audit=read(path/'eds_eval/decision-evidence-audit.json')
 check('source_compute',result['outcome_valid'] is True and comp['outcome']=='completed',arm+':terminal_invalid')
 check('source_compute',audit['accepted'] is True and audit['evidence_complete'] is True and audit['errors']==[],arm+':audit_not_accepted')
 check('source_compute',result['source_commit']==HEAD and result['identity']['profile']==arm and result['identity']['task_id']==0 and result['identity']['env_seed']==1969522881,arm+':identity_mismatch')
 check('source_compute',comp['task_id']==0 and comp['episode_seed']==1969522881 and comp['episode_id']==0,arm+':compute_identity_mismatch')
 check('source_compute',all(comp[x] is True for x in ('policy_counters_available','provider_counters_available','perception_counters_available')),arm+':counter_unavailable')
 check('source_compute',len(metrics)==comp['guided_chunks'],arm+':guided_count')
 check('source_compute',len(comp['model_forward_batch_sizes'])==comp['model_forward_calls'] and sum(comp['model_forward_batch_sizes'])==comp['model_batch_rows'],arm+':model_batch_accounting')
 roles=audit['observed_scoring_roles'];n=len(metrics)
 check('source_compute',roles.get('canonical_initial')==n and roles.get('canonical_offspring')==10*n,arm+':canonical_role_counts')
 check('source_compute',comp['reward_scoring_batches']==sum(roles.values()) and comp['reward_calls']==comp['reward_evaluations']==16*sum(roles.values()),arm+':actual_reward_accounting')
 check('source_compute',comp['provider_failed_calls']==0 and result['stage_failed_queries']==0 and comp['provider_token_usage_complete'] is True,arm+':stage_transport_invalid')
 for m in metrics:
  tag=arm+':s'+str(m['global_step'])
  check('source_compute',m['score_call_count']==11 and m['search_evaluation_count']==176,tag+':canonical_budget')
  check('source_compute',m['qd_archive_enabled']==(arm!='C0') and m['qd_evaluation_count']==(0 if arm=='C0' else 176),tag+':archive_identity')
  check('finite_action',all(type(m.get(k)) is int and m[k]==0 for k in zero_fields),tag+':invariant_or_finite_violation')
  check('finite_action',isinstance(m['action_mask_violation_max'],(float,int)) and math.isfinite(m['action_mask_violation_max']) and 0<=m['action_mask_violation_max']<=1e-6,tag+':mask_violation')
  check('finite_action',m['execution_horizon_resolved']==8,tag+':execution_horizon')
  check('source_compute',not any(k.endswith('_fallback_used') and v is True for k,v in m.items()),tag+':unapproved_fallback')
  if arm!='N2': check('source_compute',m.get('qd_quality_mode','provider')=='provider',tag+':control_quality_changed')
 data[arm]=(path,result,comp,metrics,audit)
 summary.append({'arm':arm,'attempt_id':result['attempt_id'],'retry_of':result['retry_of'],'outcome_valid':result['outcome_valid'],'task_success':result['success'],'task_failure':result['task_failure'],'gpu_process_wall_seconds':result['gpu_process_wall_seconds'],'source_commit':result['source_commit'],'n2_frozen_identity':result['n2_frozen_identity'],'plan_sha256':result['plan_sha256'],'init_row_sha256':result['init_row_sha256'],'audit_accepted':audit['accepted'],'audit_evidence_complete':audit['evidence_complete'],'audit_errors':audit['errors'],'executed_actions':audit['observed_counts']['executed_action'],'guided_chunks':comp['guided_chunks'],'unguided_chunks':comp['unguided_chunks'],'candidate_evaluations':sum(m['search_evaluation_count'] for m in metrics),'canonical_batches':11*n,'actual_scoring_roles':roles,'model_forward_calls':comp['model_forward_calls'],'model_batch_rows':comp['model_batch_rows'],'reward_calls':comp['reward_calls'],'reward_scoring_batches':comp['reward_scoring_batches'],'rbf_gradient_calls':comp['rbf_gradient_calls'],'stage_successful_queries':result['stage_successful_queries'],'stage_failed_queries':result['stage_failed_queries'],'finite_and_invariant_rows_checked':n})
check('source_compute',all(x['n2_frozen_identity']==summary[0]['n2_frozen_identity'] and x['init_row_sha256']==summary[0]['init_row_sha256'] for x in summary),'shared_frozen_condition_mismatch')

path,result,comp,metrics,original_audit=data['N2'];ep=path/'eds_eval/decision_evidence/episode_000'
status=read(ep/'status.json');refs=lines(ep/'events.jsonl')
assert status['complete'] and not status['failed'] and not status['pending_action']
spec=importlib.util.spec_from_file_location('n2_frozen_audit',W/'scripts/audit_decision_evidence.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
fresh=module.audit_episode(ep,path/'eds_eval/episode_compute.jsonl')
check('source_compute',fresh['accepted'] and fresh['evidence_complete'] and not fresh['errors'],'N2:fresh_audit_failed')
# Only N2 bundles are opened. Controls use accepted JSON summaries above.
steps={m['global_step'] for m in metrics};ids={f'e0:d{step//8+1}:s{step}' for step in steps}
rows=[];opened=[]
for ref in refs:
 if not any(e['decision_id'] in ids for e in ref['events']): continue
 bundle=ep/ref['bundle'];assert sha(bundle)==ref['sha256']
 obj=torch.load(bundle,map_location='cpu',weights_only=True)
 rows.extend(e for e in obj['events'] if e['decision_id'] in ids)
 opened.append({'bundle':ref['bundle'],'sha256':ref['sha256']})
byid=collections.defaultdict(list)
for row in rows: byid[row['decision_id']].append(row)
analyses=[]
for m in metrics:
 step=m['global_step'];did=f'e0:d{step//8+1}:s{step}';events=byid[did];kinds=collections.defaultdict(list)
 for e in events:kinds[e['event']].append(e)
 ctx=kinds['decision_context'][0]['values'];candidates=kinds['canonical_candidate_batch'];final=kinds['final_selection'][0]['values'];tag='N2:s'+str(step)
 active=(m['qd_quality_mode']=='executed_prefix_v1' and m['qd_quality_applicable'] is True and m['qd_quality_reason']=='recognized_weighted_distance_template' and m['qd_archive_active_for_chunk'] is True)
 check('substantive_qd_activation',active,tag+':quality_inactive_or_unknown')
 check('source_compute',len(candidates)==11 and [e['values']['iter_idx'] for e in candidates]==list(range(-1,10)),tag+':canonical_batch_sequence')
 check('source_compute',len(ctx['providers'])==1 and m['qd_quality_target_index']==0 and len(m['qd_quality_identity']['source_text_sha256'])==64,tag+':semantic_identity')
 check('source_compute',m['qd_quality_identity']['source_text_sha256']==ctx['providers'][0]['source_text_sha256'],tag+':source_identity_join')
 canonical={};canonical_by_iter={};all_occurrences=0;changed=0
 for e in candidates:
  v=e['values'];acts=v['candidates'];q=v['effective_quality'];raw=v['raw_provider_quality'];it=v['iter_idx']
  assert tuple(acts.shape)==(16,64,128) and acts.dtype==torch.bfloat16 and tuple(q.shape)==tuple(raw.shape)==(16,)
  check('raw_stage_separation',q.dtype==raw.dtype==acts.dtype and finite(q) and finite(raw),tag+':canonical_native_dtype')
  check('substantive_qd_activation',v.get('quality_mode')=='executed_prefix_v1',tag+':mixed_quality_mode')
  listed=m['qd_quality_batches'][it+1]
  check('source_compute',listed['iter_idx']==it and listed['quality']==q.float().tolist() and listed['raw_provider_quality']==raw.float().tolist(),tag+':metric_batch_join')
  changed+=int((q!=raw).sum())
  occurrence=[]
  for i,a in enumerate(acts):
   key=native_key(a);fingerprint=fp(a);assert fingerprint==v['canonical_fingerprints'][i]==listed['fingerprints'][i]
   entry={'native_sha256':key[2],'fingerprint':fingerprint,'quality':q[i].item(),'raw':raw[i].item(),'sequence':e['sequence'],'candidate_index':i,'iter_idx':it,'occurrence_id':v['occurrence_ids'][i]}
   canonical.setdefault(key,[]).append(entry);occurrence.append(entry);all_occurrences+=1
  canonical_by_iter[it]=occurrence
 check('source_compute',all_occurrences==176,tag+':native_canonical_count')
 check('substantive_qd_activation',changed==m['qd_quality_changed_candidates'],tag+':changed_count_mismatch')
 # Join each actual effective quality back to its original provider return and aggregate.
 for e in kinds['scoring_inputs']:
  v=e['values'];sid=e['sequence'];scope=v['scoring_scope'];iscanonical=scope['role'].startswith('canonical_')
  effective=next(r['values'] for r in kinds['effective_quality'] if r['values']['scoring_batch_id']==sid)
  aggregate=next(r['values']['aggregate_before_reward_mode'] for r in kinds['scoring_aggregate'] if r['values']['scoring_batch_id']==sid)
  returned=[r['values'] for r in kinds['provider_return'] if r['values']['scoring_batch_id']==sid]
  check('raw_stage_separation',len(returned)==16 and [x['candidate_index'] for x in returned]==list(range(16)),tag+':raw_return_rows')
  reconstructed=torch.stack([x['result'].to(dtype=aggregate.dtype).reshape(()) if torch.is_tensor(x['result']) else torch.tensor(float(x['result']),dtype=aggregate.dtype) for x in returned])
  check('raw_stage_separation',torch.equal(reconstructed,aggregate),tag+':provider_native_aggregate')
  if iscanonical:
   raw=effective['raw_provider_quality'];check('raw_stage_separation',raw.shape==aggregate.shape and raw.dtype==aggregate.dtype and torch.equal(raw,aggregate),tag+':raw_aggregate')
   it=scope['iter_idx'];c=candidates[it+1]['values']
   check('raw_stage_separation',torch.equal(v['samples'],c['candidates']) and v['samples'].dtype==c['candidates'].dtype and torch.equal(raw,c['raw_provider_quality']) and torch.equal(effective['quality'],c['effective_quality']),tag+':score_candidate_join')
  else: check('raw_stage_separation','quality_mode' not in effective and torch.equal(effective['quality'],aggregate),tag+':auxiliary_changed')
 # The final pool must match native canonical bytes, never just a float32 hash.
 pool=final['population'];raw_final=final['raw_provider_quality'];pool_entries=[]
 cells=sorted(int(x) for x in m['qd_per_cell_elite_reward_by_iter'][-1])
 assert len(cells)==len(pool) and pool.dtype==torch.bfloat16 and raw_final.dtype==torch.float32
 for index,a in enumerate(pool):
  key=native_key(a);matches=canonical.get(key,[]);assert matches
  pairset={(x['quality'],x['raw']) for x in matches};assert len(pairset)==1
  q,raw=next(iter(pairset))
  check('raw_stage_separation',raw_final[index].item()==raw,tag+':final_raw_native_binding')
  check('substantive_qd_activation',q==m['qd_per_cell_elite_reward_by_iter'][-1][str(cells[index])],tag+':final_q8_archive_binding')
  pool_entries.append({'final_index':index,'cell':cells[index],'native_dtype':str(a.dtype),'native_shape':list(a.shape),'native_sha256':key[2],'fingerprint':fp(a),'q8':q,'raw_provider_quality':raw,'canonical_occurrences':[{k:x[k] for k in ('sequence','candidate_index','iter_idx','occurrence_id')} for x in matches]})
 selected=pool_entries[final['selected_index']]
 winner=min(pool_entries,key=lambda x:(-x['q8'],x['fingerprint'],x['cell']))
 check('substantive_qd_activation',selected==winner and final['selection_rule']=='archive_global_best' and selected['q8']==final['selected_quality']==m['selected_reward']==m['qd_selected_reward'],tag+':not_q8_final_winner')
 check('substantive_qd_activation',selected['fingerprint']==final['selected_canonical_fingerprint']==m['qd_selected_action_fingerprint']==m['qd_global_best_action_fingerprint'],tag+':final_fingerprint')
 check('raw_stage_separation',selected['raw_provider_quality']==final['selected_raw_provider_quality']==m['qd_selected_raw_reward'],tag+':selected_raw')
 best_raw=max(x['raw_provider_quality'] for x in pool_entries);raw_best=[x for x in pool_entries if x['raw_provider_quality']==best_raw]
 gap=selected['raw_provider_quality']-best_raw
 check('raw_stage_separation',best_raw==m['qd_final_best_raw_reward'] and gap==m['qd_selected_raw_gap'],tag+':raw_gap')
 # Actual allocated parent rows must bind to earlier observed native candidates.
 parent_rows=kinds['archive_parent_allocation'];assert len(parent_rows)==10
 parent_binding_rows=0;parent_iterations=[]
 for e in parent_rows:
  v=e['values'];it=v['iter_idx'];ordinary=next(x['values'] for x in kinds['parent_allocation'] if x['values']['iter_idx']==it)
  check('substantive_qd_activation',sum(v['slot_counts'].values())==16 and len(v['parent_cell_ids'])==16 and m['qd_parent_slots_by_cell_by_iter'][it]==v['slot_counts'],tag+':parent_slots')
  pop=ordinary['source_population'];assert len(pop)==16
  for i,a in enumerate(pop):
   key=native_key(a);matches=[x for x in canonical.get(key,[]) if x['iter_idx']<it]
   pair=(v['parent_rewards'][i].item(),v['parent_raw_rewards'][i].item())
   check('raw_stage_separation',pair in {(x['quality'],x['raw']) for x in matches},tag+':parent_raw_lineage')
   check('substantive_qd_activation',fp(a)==v['parent_fingerprints'][i]==ordinary['source_fingerprints'][i] and v['parent_costs'][i].item()==-pair[0],tag+':parent_quality_binding')
   parent_binding_rows+=1
  parent_iterations.append({'iter_idx':it,'slots':sum(v['slot_counts'].values()),'parent_rows':len(pop)})
 strict=gap<0 and all(x['native_sha256']!=selected['native_sha256'] and x['fingerprint']!=selected['fingerprint'] for x in raw_best)
 analyses.append({'decision_id':did,'global_step':step,'stage':ctx['stage'],'quality_applicable':active,'target_index':m['qd_quality_target_index'],'provider_identity':m['qd_quality_identity'],'canonical_candidates':all_occurrences,'canonical_batches':len(candidates),'auxiliary_batches':sum(x['values']['scoring_scope']['role']=='auxiliary_pretest' for x in kinds['scoring_inputs']),'changed_candidates':changed,'archive_invariants':{k:m[k] for k in zero_fields if k.startswith('qd_')},'final_pool_size':len(pool_entries),'selected':selected,'same_final_pool_raw_best':raw_best,'selected_raw_gap':gap,'q8_maximizers':[x['fingerprint'] for x in pool_entries if x['q8']==winner['q8']],'q8_tie_rule_verified':'(-stored Q8, canonical fingerprint, cell)','strict_same_pool_quality_tradeoff_witness':strict,'parent_iterations':parent_iterations,'parent_native_raw_binding_rows':parent_binding_rows,'all_final_pool_entries':pool_entries})
check('substantive_qd_activation',any(x['strict_same_pool_quality_tradeoff_witness'] for x in analyses),'no_actual_quality_dependent_selection_witness')
assert not torch.cuda.is_initialized()
report={'schema':'n2-first-three-checkpoint-review-v1','source_commit':HEAD,'scope':'CPU review of three accepted terminal JSON summaries and only the accepted N2 native bundles; no invalid Q0 bundle, provider, projection, model, simulator or GPU call', 'gates':{k:{'status':'PASS' if not v else 'FAIL','violations':v} for k,v in violations.items()},'arms':summary,'n2_decisions':analyses,'fresh_n2_audit':{k:fresh[k] for k in ('accepted','evidence_complete','errors','observed_counts','observed_scoring_roles')},'n2_bundle_verification':{'index_sha256':hashes[str(ep/'events.jsonl')],'fresh_audit_all_bundle_count':len(refs),'guided_bundle_count_opened_for_review':len(opened),'guided_bundle_manifest_sha256':hashlib.sha256(json.dumps(opened,sort_keys=True).encode()).hexdigest()},'raw_stage_evidence_level':'Frozen production source routes the selected raw value/vector at core/rdt_policy_steer.py:6985 to the unchanged normalization; FP32/BF16 CPU integration tests and actual native raw-selected joins verify this contract. Actual normalized Stage call parameters are not separately recorded.','limitations':['No task-success gate was added; task0 outcomes are reported separately and do not establish benefit.','Original archive insertion occurrence is not directly recorded; review verifies native content and raw/Q8 consistency across all matching canonical occurrences, not a unique ancestry where duplicates exist.','No production projector-call counter exists; unchanged calls rely on frozen code and prior CPU regression, not a new online counter.','C0 and valid recovered Q0 bundles were not reopened; their accepted audit JSON supports action/prefix completeness.','Stage trajectories can differ after changed actions; direct normalized Stage inputs remain unobserved.','The prior invalid Q0 attempt remains linked in retry_of and is not replaced or analyzed here.','This is a checkpoint review, not release authorization or N2 performance promotion.'],'cuda_initialized_before':False,'cuda_initialized_after':torch.cuda.is_initialized(),'input_sha256':hashes,'review_script_sha256':sha(Path(__file__))}
OUT.mkdir(parents=True,exist_ok=True)
with (OUT/'review-v1.json').open('x') as f:json.dump(report,f,indent=2,allow_nan=False);f.write('\n')
first=next(x for x in analyses if x['global_step']==0);chosen=first['selected'];best=first['same_final_pool_raw_best'][0]
md=f'''# N2 first-three checkpoint review v1

Four existing gates: {', '.join(k+'='+v['status'] for k,v in report['gates'].items())}. Source `{HEAD}`; CPU only, CUDA remained uninitialized. JSON contains source/input hashes and all exact native joins.

C0, valid recovered Q0, and N2 all have condition-valid completed terminals and accepted complete audits. Their task outcomes are all failure (0/1 each), reported independently of these correctness gates. Guided/unguided chunks are 29/61, 52/38, and 3/87; each executed 720 actions. The earlier invalid Q0 remains linked and was not opened.

N2 decisions at steps 0, 8, 16 all recognize the frozen weighted-distance template at target index 0, activate the QD archive, and record 176 canonical candidates / 11 batches. Changed native quality counts are 169, 175, 176. All archive invariant counters are zero. Each decision has ten actual parent allocations of 16 rows; 480 parent raw/Q8 associations were checked against earlier native canonical candidates. Canonical provider returns, native aggregate, internal Q8, final stored raw vector, selected identity and metric values agree. Fifteen auxiliary batches retain original provider quality.

At step 0 the same 16-entry final pool gives a strict tradeoff witness. Q8 selected fingerprint `{chosen['fingerprint']}` (index {chosen['final_index']}, native SHA `{chosen['native_sha256']}`), Q8 {chosen['q8']}, original raw {chosen['raw_provider_quality']}. The raw-best candidate fingerprint `{best['fingerprint']}` (index {best['final_index']}, native SHA `{best['native_sha256']}`) has raw {best['raw_provider_quality']} and Q8 {best['q8']}. Native BF16 actions differ. The selected raw gap is {first['selected_raw_gap']}; the actual winner matches the frozen Q8/fingerprint/cell ordering. Step 8 and 16 raw gaps are zero; no extra witness is invented for them.

Raw-to-Stage isolation is supported by these actual raw-selected joins plus the frozen source path and prior FP32/BF16 CPU tests. Production does not separately record the normalized Stage argument, so this is not a direct measurement of every Stage threshold input. No projector runtime counter exists; unchanged call structure is a source/CPU-test claim. C0/Q0 summaries were checked without reading their bundles. No new success/coverage threshold, retry, release attestation, or performance claim is made.
'''
with (OUT/'review-v1.md').open('x') as f:f.write(md)
print(json.dumps({'gates':report['gates'],'step0':{'selected_raw':chosen['raw_provider_quality'],'selected_q8':chosen['q8'],'raw_best_raw':best['raw_provider_quality'],'raw_best_q8':best['q8'],'raw_gap':first['selected_raw_gap'],'distinct_native':chosen['native_sha256']!=best['native_sha256']},'json':str(OUT/'review-v1.json'),'json_sha256':sha(OUT/'review-v1.json'),'md_sha256':sha(OUT/'review-v1.md'),'cuda_initialized':torch.cuda.is_initialized()},allow_nan=False))
