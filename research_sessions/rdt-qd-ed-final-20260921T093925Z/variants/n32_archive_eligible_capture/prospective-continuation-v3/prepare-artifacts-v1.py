"""Bounded CPU document preparation; no application imports, execution, or state writes."""
import json, hashlib, datetime, subprocess, copy
from pathlib import Path
OUT=Path(__file__).resolve().parent
BASE=OUT.parents[2]
ROOT=BASE/'study_worktree'
OLD=OUT.parent/'root-recovery-release-v2'
IMPL=OUT.parent/'implementation_worktree'
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):
 p=Path(p); return {'path':str(p),'sha256':digest(p),'bytes':p.stat().st_size}
def read(p): return json.loads(Path(p).read_text())
def guard():
 assert not (BASE/'autonomy_20261004/STOP').exists() and not (BASE/'autonomy_20261004/STOP').is_symlink(), 'STOP: no new work'
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-10T17:42:00+00:00'), 'deadline'
def write(name,obj):
 guard();p=OUT/name;assert p.parent==OUT
 p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n');return ref(p)
guard()
auth=read(OUT/'authority-v1.json');scope=read(auth['scope']['path'])
assert digest(auth['scope']['path'])==auth['scope']['sha256']
for k in ['parent_plan','terminal_review','transport_review']: assert digest(scope[k]['path'])==scope[k]['sha256']
p=read(scope['parent_plan']['path']); review=read(scope['terminal_review']['path']); transport=read(scope['transport_review']['path'])
proto=read(OLD/'protocol-v1.json');budget=read(OLD/'budget-authority-v1.json');runtime=read(p['runtime']['path'])
assert digest(p['runtime']['path'])==p['runtime']['sha256']
source=p['source'];sidx={v['path']:v['sha256'] for v in source['files']}
head=subprocess.check_output(['git','-C',str(IMPL),'rev-parse','HEAD'],text=True).strip();assert head==scope['source_commit']==source['commit']
inputs={k:ref(OLD/k) for k in ['plan.frozen.v1.json','protocol-v1.json','budget-authority-v1.json','execution-release-v1.json','root-production-review-v1.json','worker-entrypoints-v1.json','root-review-evidence-v1.json','owning-checkout-rebind-v1.json','adoption-reconciliation-v1.json','pre-adoption-validation-v1.json']}
inputs.update({'authority':ref(OUT/'authority-v1.json'),'scope':ref(auth['scope']['path']),'terminal_review':ref(scope['terminal_review']['path']),'transport_review':ref(scope['transport_review']['path']),'terminal_reconciliation':ref(BASE/'autonomy_20261004/turns/000443/terminal-reconciliation.json'),'instructions':ref(ROOT/'AGENTS.md'),'runtime':ref(p['runtime']['path'])})
# Fixed shallow receipt boundary: do not recursively open tensor bundles, caches, journals or protected splits.
checks=[]
def check(label,ok):
 checks.append({'check':label,'passed':bool(ok)})
def verify(r):
 a=ref(r['path']);check('hash:'+r['path'],a['sha256']==r['sha256'] and ('bytes' not in r or a['bytes']==r['bytes']));return read(r['path'])
rows={x['episode_key']:x for x in p['episodes']}; historical=[];terminals=[]
provider=runtime['frozen_stage_provider']; transport_keys=['auth_mode','backend','cli_path','model','public_config_sha256','reasoning_effort','timeout_seconds','allow_recovered_error_events','disabled_skill_paths']
for cell in review['cells']:
 guard();old=cell['attempt_id'];row=rows[old];n=verify(cell['native_receipt']);g=verify(cell['generic_audit']); sr=ref(cell['stage_events']['path']);check(old+':stage_events_hash',sr['sha256']==cell['stage_events']['sha256'])
 m=verify(n['expected_manifest']);cx=verify(n['context']);o=Path(m['output_dir']);t=read(o/'attempt-result.json');cmd=read(o/'command.json');process=read(o/'process.json');terminals.append(t)
 check(old+':row',row==n['row']==m['row'])
 check(old+':source',n['source']==source==m['source'])
 check(old+':runtime',m['runtime']==p['runtime'] and t['runtime_manifest_sha256']==p['runtime']['sha256'] and t['runtime_inventory_sha256']==p['runtime_inventory_sha256'])
 check(old+':plan',n['plan']['sha256']==scope['parent_plan']['sha256']==t['plan_sha256'] and cx['plan']==n['plan'])
 check(old+':command',cmd['main_argv']==m['argv'] and cx['main_argv']==m['argv'][1:] and cmd['context']==n['context'] and cmd['argv']==[m['argv'][0],'-m','scripts.qd_ed_n32_worker','--context',n['context']['path'],'--context-sha256',n['context']['sha256']])
 check(old+':receipt_identity',old==n['attempt_id']==t['attempt_id']==t['episode_key']==cx['attempt_id']==cx['episode_key'] and process['attempt_id']==old)
 check(old+':audit',n['accepted'] is True and g['accepted'] is True and n['audit_report']['sha256']==cell['generic_audit']['sha256'] and n['process_unchanged'] is True and n['process']=={k:process[k] for k in ['pid','proc_start_ticks','boot_id']})
 check(old+':cuda',n['worker_cuda']['physical_gpu']==7 and n['worker_cuda']['uuid']==scope['gpu_uuid'])
 check(old+':provider',all(t['stage_transport'][k]==provider[k] for k in transport_keys) and t['stage_backend']==provider['backend'] and t['stage_model']==provider['model'])
 check(old+':loaded_source',all(sidx.get(v['path'])==v['sha256'] for phase in ['loaded_before','loaded_after'] for v in n[phase].values()))
 check(old+':terminal_class', (cell['event']=='valid' and t['event']=='valid' and t['outcome_valid'] is True and t['required_cost_telemetry_complete'] is True and t['success'] is False) or (cell['event']!='valid' and t['outcome_valid'] is False and t['success'] is None))
 historical.append({**cell,'old_attempt_id':old,'new_attempt_id':old if cell['event']=='valid' else None,'semantic_cell':{k:row[k] for k in ['task_id','profile','split','seed_block','env_seed','policy_seed','init_index','init_row_sha256','init_file_sha256','bddl_sha256']},'original_row':row,'terminal_receipt':ref(o/'attempt-result.json'),'command_receipt':ref(o/'command.json'),'context':n['context'],'process_receipt':ref(o/'process.json'),'expected_manifest':n['expected_manifest'],'source_commit':source['commit'],'runtime':p['runtime'],'gpu_hours_retained':t['gpu_process_wall_seconds']/3600,'budget_bucket_retained':t['budget_bucket'],'denominator_eligible':cell['event']=='valid','replay_permitted':False})
# Verify only source code used for contract review, not the broad inventory or prohibited design document.
contract_files=['scripts/qd_ed_n32_contract.py','scripts/qd_ed_n32_supervise.py','scripts/qd_ed_n32_release.py','scripts/qd_ed_n32_runner.py','scripts/qd_ed_n32_worker.py','scripts/qd_ed_n32_bridge.py']
code_refs={x:ref(IMPL/x) for x in contract_files}
for x,v in code_refs.items():check('frozen contract code:'+x,v['sha256']==sidx[x])
accepted=[x for x in historical if x['denominator_eligible']];invalid=[x for x in historical if not x['denominator_eligible']]
check('14 accepted/1 invalid',len(accepted)==14 and len(invalid)==1)
cohort='N32R3_ARCHIVE_ELIGIBLE_CAPTURE_CONTINUATION_DEV_20261008';proposed=[];commands=[]
for oldrow in p['episodes'][14:]:
 old=oldrow['episode_key'];rec=oldrow['task_id']==4
 new=f'n32r3_{"recovery" if rec else "dev"}_t{oldrow["task_id"]:02d}_{oldrow["profile"].lower()}_20261008'
 row={**oldrow,'episode_key':new,'iteration':cohort,'budget_bucket':'recovery' if rec else oldrow['budget_bucket']}
 mref=p['expected_manifests'][old];m=verify(mref)
 check(old+':prospective_manifest_identity',m['row']==oldrow and m['source']==source and m['runtime']==p['runtime'])
 # Exact identity/output substitution only; candidate commands are data, never launched.
 newout=str(OUT/'prospective-artifacts'/'attempts'/new)
 argv=[a.replace(m['output_dir'],newout).replace(old,new) for a in m['argv']]
 changes=[{'index':i,'old':a,'new':argv[i]} for i,a in enumerate(m['argv']) if a!=argv[i]]
 allowed={'hydra.run.dir','main.eds_eval.output_dir','main.eds_eval.job_id','main.eds_mechanism_pretest.output_dir','main.eds_mechanism_pretest.run_id','main.eds_config.n32_runtime_binding'}
 check(old+':only_identity_command_changes',all(x['old'].split('=',1)[0] in allowed for x in changes))
 semantic={k:v for k,v in oldrow.items() if k not in ['episode_key','iteration','budget_bucket']}
 check(old+':semantic_identity',semantic=={k:v for k,v in row.items() if k not in ['episode_key','iteration','budget_bucket']})
 check(old+':untouched_output',rec or not Path(m['output_dir']).exists())
 proposed.append({'old_attempt_id':old,'new_attempt_id':new,'relation':'explicit_recovery_of_invalid' if rec else 'undispatched_primary_identity_migration','recovery_of':old if rec else None,'retry_of':None,'old_row':oldrow,'proposed_row':row,'semantic_continuity':semantic,'parent_expected_manifest':mref,'source_commit':source['commit'],'runtime':p['runtime'],'native_receipt':None,'generic_audit':None,'receipt_status':'NOT_DISPATCHED_NO_RECEIPTS','release_enabled':False})
 commands.append({'old_attempt_id':old,'new_attempt_id':new,'parent_expected_manifest':mref,'old_argv':m['argv'],'proposed_argv':argv,'exact_changes':changes,'proposed_output_dir':newout,'release_enabled':False,'external_manifest_status':'REQUIRES_FUTURE_AUTHORIZED_COMPOSITION_AND_HASH_REVIEW','old_composed_config_sha256':m['composed_config_sha256'],'old_expected_runtime':m['expected_runtime']})
check('16 unique proposals',len(proposed)==16 and len({x['new_attempt_id'] for x in proposed})==16)
check('no accepted replay',not ({x['new_attempt_id'] for x in proposed}&{x['old_attempt_id'] for x in historical}))
check('one frozen provider condition',len({t['stage_condition'] for t in terminals})==1)
check('retained GPU arithmetic',abs(budget['retained_history']['gpu_hours_consumed']+sum(t['gpu_process_wall_seconds']/3600 for t in terminals)-scope['gpu_hour_arithmetic']['spent_retained'])<1e-9)
invalid[0]['proposed_recovery_attempt_id']=proposed[0]['new_attempt_id']
failures=[x for x in checks if not x['passed']]
proof=write('continuity-evidence-v1.json',{'schema':'n32r3-bounded-continuity-evidence-v1','release_enabled':False,'source_head':head,'inputs':inputs,'contract_code':code_refs,'checks':checks,'failures':failures,'status':'HISTORICAL_RECEIPT_AND_PROPOSED_SEMANTIC_BINDINGS_VERIFIED' if not failures else 'BLOCKED_CONTINUITY','provider_contract':provider,'current_account_rule':'Only current-login official account; no fallback; no credentials read or provider call performed. Account continuity beyond persisted provider attestations is not independently established.','seed_plan_reference_only':{'path':p['seed_plan_path'],'sha256':p['seed_plan_sha256']},'runtime_inventory_reference_only':{'path':p['runtime_inventory_path'],'sha256':p['runtime_inventory_sha256']},'verification_boundary':'Shallow native/generic/terminal/context/command/expected-manifest bindings and existing reviews. No tensor audit replay, runtime cache scan, protected seed read, ledger scan, provider probe or current GPU admission. Future admission must recheck runtime/source/provider.'})
cmdref=write('command-candidates-v1.json',{'schema':'n32r3-command-candidates-NONEXECUTABLE-v1','release_enabled':False,'commands':commands})
mapref=write('carry-forward-map-v1.json',{'schema':'n32r3-carry-forward-map-v1','node_id':'15.2','release_enabled':False,'pooling_authorized':False,'parent_plan':scope['parent_plan'],'terminal_review':scope['terminal_review'],'continuity_evidence':proof,'accepted_cells':accepted,'old_invalid_cell':invalid[0],'proposed_cells':proposed,'command_candidates':cmdref,'denominator_rule':'At most one accepted valid result per frozen task/profile/seed/init/source/runtime/provider semantic cell. Preserve 14 old identities unchanged. The old invalid task4 N32 never enters denominator; only its separately audited recovery may fill that cell. 14+16=30 maximum, contingent on every future audit and root approval.','historical_transport_cause':'Unknown; persisted errors omit raw provider text. Successful current probe does not prove historical reliability or Stage recognition accuracy.','continuity_failures':failures})
add=scope['attempt_arithmetic'];hours=scope['gpu_hour_arithmetic']; before=budget['retained_history'];total=sum(t['gpu_process_wall_seconds']/3600 for t in terminals)
check('retained GPU arithmetic',abs(before['gpu_hours_consumed']+total-hours['spent_retained'])<1e-9)
by={**before['by_bucket']};bh={**before['gpu_hours_by_bucket']}
for t in terminals:by[t['budget_bucket']]+=1;bh[t['budget_bucket']]+=t['gpu_process_wall_seconds']/3600
increments={'baseline':5,'development':10,'recovery':1,'validation':0,'formal':0}
account=write('accounting-amendment-candidate-v1.json',{'schema':'n32r3-accounting-amendment-candidate-v1','approved':False,'budget_adopted':False,'release_enabled':False,'basis':inputs['scope'],'historical_budget_authority':inputs['budget-authority-v1.json'],'accounting_method':'Historical approved aggregate plus 15 exact N32R2 terminal wall-time charges, cross-checked against scope; no fresh ledger scan. Root must recompute owning journals and unsettled reservations before adoption.','retained_attempts':438,'retained_gpu_hours':hours['spent_retained'],'retained_by_bucket':by,'retained_gpu_hours_by_bucket':bh,'retained_healthcheck_hours':before['gpu_healthcheck_hours'],'n32r2_episode_gpu_hours':total,'old_invalid_charge':{'attempt_id':invalid[0]['old_attempt_id'],'bucket':'development','gpu_hours':invalid[0]['gpu_hours_retained']},'original_cohort':{'cap_gpu_hours':5,'status':'EXHAUSTED_OR_CLOSED_FOR_CONTINUATION_NO_REUSE','retroactive_change':False,'note':'Recorded episode charges are 4.427539120705009 GPUh; this is not a claim of exactly 5 GPUh measured consumption. Original cohort is closed and its cap cannot authorize continuation.'},'new_continuation':{'maximum_attempts':16,'by_bucket':increments,'additional_cap_gpu_hours':8.5,'maximum_episode_hours':16*1840/3600,'remaining_cap_for_admission_overhead_hours':8.5-16*1840/3600,'all_overhead_and_cleanup_charged':True},'maximum_cumulative_attempts':454,'maximum_cumulative_gpu_hours':hours['maximum_cumulative_hours'],'bucket_remaining_after_maximum':{k:budget['caps']['buckets'][k]-by[k]-increments[k] for k in by},'global_caps_unchanged':budget['caps'],'weekly_window_unchanged':budget['weekly_window'],'effective_gpu_ceiling':min(224,budget['weekly_window']['origin_gpu_hours']+budget['weekly_window']['increment_gpu_hours']),'protected_validation_remaining_hours':hours['protected_validation_remaining_hours'],'protected_formal_remaining_hours':12,'global_unprotected_headroom_after_cap_hours':hours['unprotected_headroom_after_proposed_cap_hours'],'effective_weekly_unprotected_headroom_after_cap_hours':min(224,budget['weekly_window']['origin_gpu_hours']+budget['weekly_window']['increment_gpu_hours'])-hours['maximum_cumulative_hours']-hours['protected_validation_remaining_hours']-12,'deadline':scope['deadline'],'no_reserve_borrowing':True,'historical_charges_retained':True})
protocol=write('prospective-protocol-v1.json',{'schema':'n32r3-prospective-protocol-candidate-v1','release_enabled':False,'executable_release':False,'cohort':cohort,'node_id':'15.2','parent_protocol':inputs['protocol-v1.json'],'source_commit':source['commit'],'runtime':p['runtime'],'carry_forward_map':mapref,'new_attempts':[x['proposed_row'] for x in proposed],'recovery_authorization':'Exactly one prospective explicit task4 N32 recovery, subject to detached root adoption; not an automatic recovery mechanism. Any new invalid stops.','automatic_recoveries':0,'promotion':proto['promotion'],'futility':proto['futility'],'futility_formula':'At complete valid task triples only: candidate_successes + (10 - complete_valid_triples) < 5 => stop. Missing/invalid triples never count as completed. Evaluate after recovered task4 joins retained C0/Q0, then after each task5-9 triple.','worker_contract':p['worker_contract'],'deadline':scope['deadline'],'stop_path':p['stop_path'],'physical_gpu':7,'gpu_uuid':scope['gpu_uuid'],'episode_seconds_including_audits':1800,'cleanup_seconds':40,'additional_continuation_cap_gpu_hours':8.5,'original_cohort_cap_gpu_hours_unchanged':5,'accounting_amendment':account,'provider_rule':'Frozen official codex_cli / current-login account only, no account/provider fallback; preserve all provider configuration and Unknown HTTP telemetry.','scientific_changes':None,'validation_authorized':False,'formal_authorized':False,'halt_rule':'STOP or deadline means no new work. Future dispatch requires full 1840 seconds before deadline and fresh idle assigned GPU admission.'})
plan=write('plan-candidate-v1.json',{'schema':'n32r3-plan-candidate-NONEXECUTABLE-v1','frozen':False,'release_enabled':False,'executable_release':False,'approved':False,'node_id':'15.2','cohort':cohort,'parent_plan':scope['parent_plan'],'source':source,'runtime':p['runtime'],'owning_worktree':p['worktree'],'preparation_worktree':str(IMPL),'artifact_root_candidate':str(OUT/'prospective-artifacts'),'episodes':[x['proposed_row'] for x in proposed],'carry_forward_map':mapref,'command_candidates':cmdref,'protocol':protocol,'accounting_amendment':account,'limits':{'new_attempts':16,'baseline':5,'development':10,'recovery':1,'automatic_recoveries':0,'continuation_gpu_seconds':30600,'episode_seconds':1800,'cleanup_seconds':40,'physical_gpu':7,'gpu_uuid':scope['gpu_uuid']},'deadline':scope['deadline'],'stop_path':p['stop_path'],'worker_contract':p['worker_contract'],'promotion':proto['promotion'],'phase_authorization':{'dev':False,'validation':False,'formal':False},'expected_manifests':{},'expected_manifest_status':'Not generated: existing frozen contract cannot release continuation. Commands are prospective data only; future authorized exact composition and native/source/runtime/command audits required.','scientific_changes':None,'root_review_required':True,'current_contract_compatible':False})
print(json.dumps({'historical_cells':len(historical),'accepted':len(accepted),'proposed':len(proposed),'continuity_failures':failures,'recorded_old_gpu_hours':total,'retained_by_bucket':by,'outputs':[proof,mapref,cmdref,account,protocol,plan]},indent=2))
