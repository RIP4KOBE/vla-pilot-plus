import os,json,hashlib,datetime,subprocess
from decimal import Decimal,localcontext
from pathlib import Path
from scripts import qd_ed_n36_contract as c, qd_ed_n36_stop as stop
from scripts import qd_ed_n36r2_admission as gate, qd_ed_n36r2_draft as draft
from scripts import qd_ed_final_runner as r
OUT=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001276/b5-preparation')
PREV=gate.SESSION/'autonomy_20261004/turns/001268/source-runtime-preparation'
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest()}
def write(name,d):
 p=OUT/name;p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n');return ref(p)
stop.check()
a=json.loads((OUT/'authority-v1.json').read_text())
old_ref=ref(PREV/'plan.complete-disabled-v1.json');old=json.loads(Path(old_ref['path']).read_text())
snap_record=json.loads((OUT/'current-ledger-snapshot-v1.json').read_text());snap=snap_record['snapshot']
events=r.read_events(Path(a['owner'])/'data/attempt-ledger.jsonl');resources=r.read_events(Path(a['owner'])/'data/gpu-healthcheck-ledger.jsonl')
draft_ref=json.loads(Path(old['accounting']['path']).read_text())
base_ref=draft_ref['inherited_accounting'];base=json.loads(Path(base_ref['path']).read_text())
assert base_ref['sha256']==c.ACCOUNTING_SHA and ref(base_ref['path'])['sha256']==c.ACCOUNTING_SHA
gate.preserve_charges(events)
assert snap==r.budget_snapshot(events,resources)
term=[v[-1] for v in r.event_groups(events).values()]
ht={}
for v in resources:ht[v['resource_id']]=v
assert all(v['event'] in r.TERMINAL for v in term)
assert all(v['event'] in ('completed','aborted') for v in ht.values())
D=lambda v:Decimal(str(v))
with localcontext() as ctx:
 ctx.prec=65
 total=sum((D(e['gpu_process_wall_seconds']) for e in term+list(ht.values())),Decimal(0))
 retained=D(snap['gpu_hours_consumed']);margin=D(base['cost_reconciliation']['retained_admission_margin_gpu_hours'])
 effective=D('53.08404692669838')+168
 protected={k:max(Decimal(0),D(v)-D(snap['gpu_hours_by_bucket'][k])) for k,v in c.CAPS['protected_gpu_hours'].items()}
 charge=retained+margin;after=charge+21;protected_total=sum(protected.values())
 arithmetic={k:str(v) for k,v in {'terminal_decimal_seconds':total,'terminal_decimal_hours':total/3600,
 'production_snapshot_gpu_hours':retained,'retained_margin_gpu_hours':margin,'conservative_charge_gpu_hours':charge,
 'absolute_cap_gpu_hours':D(224),'weekly_origin_gpu_hours':D('53.08404692669838'),'weekly_increment_gpu_hours':D(168),
 'effective_cap_gpu_hours':effective,'normalized_after_cohort_gpu_hours':retained+21,
 'conservative_after_cohort_gpu_hours':after,'absolute_headroom_after_cohort_gpu_hours':D(224)-after,
 'effective_headroom_after_cohort_gpu_hours':effective-after,
 'protected_validation_remaining_gpu_hours':protected['validation'],'protected_formal_remaining_gpu_hours':protected['formal'],
 'protected_total_remaining_gpu_hours':protected_total,'unprotected_effective_headroom_after_cohort_gpu_hours':effective-after-protected_total}.items()}
 calc={'schema':'n36r2-accounting-calculation-v1','release_enabled':False,'ledger_snapshot':ref(OUT/'current-ledger-snapshot-v1.json'),
 'prior_accounting':base_ref,'arithmetic':arithmetic,'decimal_policy':'Exact Decimal over recorded numeric strings. Production float snapshot retained unchanged; its slightly higher total is the conservative admission basis. No healthcheck double charge; retain only original margin.',
 'attempts':{'before':504,'addition':40,'after':544,'cap':1800,'remaining':1256,'protected_remaining':160},
 'bucket_arithmetic':[{'bucket':k,'before':snap['by_bucket'][k],'addition':10 if k=='baseline' else 30 if k=='development' else 0,'after':snap['by_bucket'][k]+(10 if k=='baseline' else 30 if k=='development' else 0),'cap':v,'remaining_after':v-snap['by_bucket'][k]-(10 if k=='baseline' else 30 if k=='development' else 0)} for k,v in c.CAPS['buckets'].items()],
 'cohort_seconds':{'episode':1800,'cleanup':40,'per_episode_reserved':1840,'cells':40,'episodes_total':73600,'healthchecks_total':1800,'contingency':200,'total':75600},
 'preserved_attempts':draft.PRESERVED,'terminal_episode_count':len(term),'terminal_healthcheck_count':len(ht),
 'fresh_healthcheck_ids':[gate.PREPARATION_ID]+['n36_healthcheck_'+x['episode_key'] for x in c.plan_rows(old)],
 'fresh_ids_absent':not any(e['resource_id'] in {gate.PREPARATION_ID}|{'n36_healthcheck_'+x['episode_key'] for x in c.plan_rows(old)} for e in resources),
 'new_attempt_ids_absent':not any(e['attempt_id'] in {x['episode_key'] for x in c.plan_rows(old)} for e in events),
 'new_budget_authority':False,'amendment_required':False,'unknown_telemetry':'Retain every unknown cost/HTTP field and invalid outcome unchanged; no inferred success, refunds or zero-cost substitutions.',
 'fresh_charge_handling':'Append fresh reserved/dispatched/terminal records to owning ledgers only after detached release under owning locks. Charge measured occupancy including audit/cleanup. Never offset invalid N36/N36R1 charges. Unknown durations or unsettled records block; failed healthcheck blocks cohort with no replay.',
 'wall_check':{'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'deadline':c.DEADLINE,'full_cohort_seconds':75600,'available_seconds':(datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))-datetime.datetime.now(datetime.timezone.utc)).total_seconds(),'per_episode_need':1840,'with_max_healthcheck_need':1900,'not_a_reservation':True}}
 calculation=write('accounting-calculation-v1.json',calc)
route={'source_cwd':str(gate.SOURCE),'owner_root':str(gate.OWNER.resolve()),'physical_gpu':7,'gpu_uuid':c.GPU_UUID}
ledger={'schema':'n36r2-prospective-accounting-v1','inherited_accounting':base_ref,'preserved_attempts':draft.PRESERVED,'caps':c.CAPS,'healthchecks':gate.HEALTH,'ledger_prefixes':a['ledger_prefixes'],'calculation':calculation,'automatic_recoveries':0,'new_budget_authority':False,'release_enabled':False}
accounting=write('accounting.prospective-disabled-v1.json',ledger)
protocol={'schema':'n36r2-prospective-protocol-v1','inherited_draft_plan':old_ref,'inherited_protocol':json.loads(Path(old['protocol']['path']).read_text())['inherited_protocol'],'accounting':accounting,'episodes':c.plan_rows(old),'protocol_review':old['protocol_review'],'healthchecks':gate.HEALTH,'resource_routing':route,'automatic_recoveries':0,'scientific_changes':False,'release_enabled':False}
protocol_ref=write('protocol.prospective-disabled-v1.json',protocol)
plan={**old,'protocol':protocol_ref,'accounting':accounting,'resource_routing':route,'b5_review':None,'source_binding_status':'STALE_PENDING_LISTED_REBINDINGS_NO_RELEASE'}
plan_ref=write('plan.unbound-disabled-v1.json',plan)
for row in plan['episodes']:
 manifest=json.loads(Path(plan['expected_manifests'][row['episode_key']]['path']).read_text())
 write('context.'+row['episode_key']+'.disabled.json',{'schema':'n36-worker-context-v1','plan':plan_ref,'release':None,'expected_manifest':plan['expected_manifests'][row['episode_key']],'episode_key':row['episode_key'],'attempt_id':row['episode_key'],'main_argv':manifest['argv'],'worker_contract':c.WORKER_CONTRACT})
c.validate_draft(plan);gate.validate_protocol(plan)
write('resource-routing-v1.json',{'schema':'n36r2-private-routing-preparation-v1','release_enabled':False,**route,
 'state':str(gate.OWNER.resolve()/'research-state.yaml'),'ledgers':a['ledger_prefixes'],
 'locks':[str(gate.OWNER.resolve()/'data'/n) for n in ('qd-ed-runner.lock','qd-ed-state.lock')],
 'operation_lock_order':'runner nonblocking then state; no locks acquired in this task',
 'cuda_egl':{'physical_gpu':7,'uuid':c.GPU_UUID,'logical_device':'cuda:0','egl_device_index':4,'independently_confirmed_now':False},
 'provider':'current official gpt-6-astra account via existing codex_cli only; no provider/login/network work in preparation',
 'import_policy':'source-only bootstrap -I -S -B; ignores inherited PYTHONPATH; explicit isolated source and three vendored package roots plus interpreter paths only; no site startup/.pth; live source attestation rejects resolved search entries outside source/interpreter prefix; no adjacent checkout paths',
 'receipt_policy':{'actual_worker_receipts_exist':False,'preflight_is_worker_evidence':False,'before':'In actual admitted worker, before Main, capture process/context/runtime_closure bound runtime, loaded source, source-execution and native-build observations using exclusive create + fsync + read-only mode. Hash-bind retained before file in final worker receipt.',
 'after':'Same PID/boot_id/start ticks, after Main and native audits, capture separate after file once; parent hashes files and checks exact embedded observations, inventories, generated-runtime ownership, CUDA UUID, controller instances, all native gates and before/after continuity. Missing/partial/tampered receipt yields INVALID and retains charge.',
 'immutability_limit':'Exclusive create and read-only mode prevent normal overwrite; SHA-256 references detect later changes. This is hash-bound retention, not filesystem WORM or protection against a privileged malicious writer.'},
 'STOP_paths':list(stop.STOP_PATHS),'deadline':c.DEADLINE,'readiness':'Future independent release must refresh source/runtime reviews and device/provider/accounting/STOP/time evidence. Historical booleans and CPU readiness are not production evidence.'})
write('preparation-checks-v1.json',{'disabled_draft_and_protocol_valid':True,'all40_contexts_release_null':True,'authority_null':plan['authority'] is None,'root_review_null':plan['root_review'] is None,'execution_release_null':plan['execution_release'] is None,'release_enabled':False,'STOP_paths':{x:os.path.lexists(x) for x in stop.STOP_PATHS},'at':datetime.datetime.now(datetime.timezone.utc).isoformat()})
print(json.dumps(arithmetic,indent=2))
