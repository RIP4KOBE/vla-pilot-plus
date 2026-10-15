import pathlib,json,sys,hashlib,datetime,shutil,yaml,subprocess
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000665').resolve();rt=out/'runtime-v2';co=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat();boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
handles=[]
for pid,start in [(268073,97715947),(843546,136259611),(802963,136182089),(805796,136191058)]:
 p=pathlib.Path(f'/proc/{pid}/stat');f=p.read_text().split(') ')[1].split() if p.exists() else None
 handles.append({'pid':pid,'boot_id':boot,'expected_start_ticks':start,'actual_start_ticks':int(f[19]) if f else None,'state':f[0] if f else 'ABSENT','identity_matches':bool(f and int(f[19])==start)})
assert all(h['identity_matches'] for h in handles[:2]) and all(h['state']=='ABSENT' for h in handles[2:])
prior=json.loads((out.parent/'000664/terminal-closure-v1.json').read_text());prefixes={}
for name,v in prior['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256'];prefixes[name]=v
new=json.loads((rt/'runtime-import-probe-v1.json').read_text());old=json.loads((out.parent/'000655/runtime-v1/runtime-import-probe-v1.json').read_text())
assert not new['errors'] and not new['uncovered_checkout_modules'] and not new['missing_files'] and not new['cuda_initialized']
assert len(new['conversion_checks'])==11 and all(x['status']=='PASS' for x in new['conversion_checks'])
log=(rt/'probe.log').read_text();assert '"runtime_attestation": "PASS"' in log and '"controller_proof": "PASS"' in log
added={k:v for k,v in new['external_modules'].items() if k not in old['external_modules']}
changed={k:v for k,v in new['external_modules'].items() if k in old['external_modules'] and v!=old['external_modules'][k]}
next_action='Prepare isolated N34R6 recovery-identity repair through executor; preserve N34R5 and all predecessor invalid charges, source science and strict audits. Regenerate prospective runtime from turn665 CPU converter probe on adopted source; freeze new accounting/protocol/manifests and independently reviewed release before idle GPU7 admission. No replay or protected evaluation.'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(root/'research-state.yaml');c=json.loads((co/'checkpoint.json').read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='f351be8831cd426515b771cc247d1cd77cdda8bb'
 snapshot=runner.budget_snapshot(runner.read_events(root/'data/attempt-ledger.jsonl'),runner.read_events(root/'data/gpu-healthcheck-ledger.jsonl'));assert snapshot==prior['budget_snapshot']
 review={'schema':'n34r6-prospective-runtime-inventory-review-v1','at':now,'source':s['source_commit'],'probe':ref(rt/'runtime-import-probe-v1.py'),'inventory':ref(rt/'runtime-import-probe-v1.json'),'candidate_closure':ref(rt/'runtime-closure.CANDIDATE-v1.json'),'strict_receipt':ref(rt/'runtime-probe-receipt-v1.json'),'probe_log':ref(rt/'probe.log'),'predecessor_closure':ref(out.parent/'000664/terminal-closure-v1.json'),'conversion_checks':new['conversion_checks'],'serialization_checks':new['serialization_checks'],'added_modules':added,'changed_modules':changed,'removed_modules':sorted(set(old['external_modules'])-set(new['external_modules'])),'cpu_status':'PASS','controller_semantics':'PASS','cuda_initialized':False,'gpu_dispatched':False,'probe_exit_code':0,'initial_failed_probe':ref(out/'runtime-v1/runtime-import-probe-v1.py'),'initial_failed_probe_log':ref(out/'runtime-v1/probe.log'),'root_cause':'Prior probe covered five array and pointer conversions but omitted null/scalar/string lazy handlers. Eleven representative CPU conversions now tested. Initial local probe failed on double conversion of ctypes scalar; preserved runtime-v1 log, then corrected probe to call from_param on original ctypes scalar. No benchmark changes.','scope':'CPU synthetic array conversion and serialization, imports and frozen config composition only. No environment construction, model load, GL context, GPU, provider, credentials, protected results or native receipt-derived trust. No scientific code changes.','native_runtime_completeness':'UNPROVEN_UNTIL_FRESH_AUDITED_EXECUTION','ledger_prefixes':prefixes,'budget_snapshot':snapshot,'old_charges_preserved':True,'release_enabled':False,'target_met':False,'next_action':next_action}
 write(out/'runtime-inventory-review-v1.json',review);binding=ref(out/'runtime-inventory-review-v1.json')
 for p in [root/'research-state.yaml',co/'checkpoint.json',co/'idea_tree.json']:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,c]:obj.update(n34r6_runtime_inventory_review=binding,status='N34R6_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',n34_continuation_status='N34R6_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',automatic_gpu_dispatch_authorized=False,next_action=next_action,updated_at=now)
 p=root/'research-state.yaml';t=p.with_suffix('.tmp');t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(p);write(co/'checkpoint.json',c)
 tree=json.loads((co/'idea_tree.json').read_text());tree['nodes']['15.4'].update(n34r6_runtime_inventory_review=binding,result='N34R5 invalid retained. Prospective CPU array/pointer/null/scalar/string conversions all PASS; additional lazy OpenGL modules bound and strict runtime attestation PASS. N34R6 identity repair and new reviewed release pending; native completeness and efficacy unproven.');write(co/'idea_tree.json',tree)
 write(out/'end-reconciliation-v1.json',{'at':now,'source':s['source_commit'],'handles':handles,'ledger_prefixes':prefixes,'review':binding,'driver_stop_present':(root.parent/'autonomy_20261004/STOP').exists(),'authorization_deadline':'2026-10-11T11:13:13Z','target_met':False,'next_action':next_action})
 (out/'operational-summary.md').write_text(f'''Turn665 — {now}

Current source {s['source_commit']}; scientific source 1065f38122379a515b60a9a424f574330405b66f unchanged. Handoff/authority/context/completion contract verified. Prior turn664 completed normally and terminal closure matches exact owning ledger prefix. Driver268073/start97715947 and coordinator843546/start136259611 live on boot {boot}; former controller802963 and worker805796 absent. STOP absent; deadline 2026-10-11T11:13:13Z. No active cohort.

Completed CPU-only runtime diagnosis: eleven synthetic OpenGL conversions PASS including None, int, float, ctypes scalar, bytes and str. Existing serialization checks and strict runtime attestation/controller semantics PASS; CUDA uninitialized. Probe, candidate closure and review hash-bound under this turn. No benchmark source mutation, dispatch, ledger charge, scientific threshold change, process signal, or driver/coordinator lock acquisition. State/checkpoint/tree reference review. Initial CPU probe failure retained in runtime-v1; corrected probe and strict attestation in runtime-v2. All {snapshot['dispatched']} attempts and {snapshot['gpu_hours_consumed']:.12f} GPUh retained.

Next bounded step: {next_action}

Unresolved: full native runtime coverage, accepted matched Dev evidence, scientific promotion, validation20/formal10/required ablations and hash-bound original-goal completion. CPU coverage is not task efficacy. Driver continues.
''')
 print(json.dumps({'review':binding,'added_modules':list(added),'changed_modules':list(changed),'budget':snapshot}))
