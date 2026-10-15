import pathlib,json,sys,hashlib,datetime,shutil,subprocess,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000695').resolve();rt=out/'runtime-v1';co=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
prior=json.loads((out.parent/'000694/terminal-closure-v1.json').read_text())
for name,v in prior['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
new=json.loads((rt/'runtime-import-probe-v1.json').read_text());old=json.loads((out.parent/'000685/runtime-v1/runtime-import-probe-v1.json').read_text())
assert not new['errors'] and not new['uncovered_checkout_modules'] and not new['missing_files'] and not new['cuda_initialized']
assert len(new['jit_checks'])==6 and all(x['status']=='PASS' for x in new['jit_checks'])
log=(rt/'probe.log').read_text();assert '"runtime_attestation": "PASS"' in log and '"controller_proof": "PASS"' in log
added={k:v for k,v in new['external_modules'].items() if k not in old['external_modules']}
assert 'dinov2' in added and 'dinov2.models.vision_transformer' in added
assert new['protobuf_checks'][0]['synthetic_model_roundtrip']=='PASS'
next_action='Prepare isolated N34R9 recovery-identity repair through executor, preserving nine invalid N34 charges and strict audits. Regenerate prospective runtime using turn695 local Torch Hub/DINOv2 import probe on adopted source, freeze new accounting/protocol/manifests and independently reviewed release before idle GPU7 admission. No replay or protected evaluation.'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(root/'research-state.yaml');c=json.loads((co/'checkpoint.json').read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='28fbcba43b513bd5f4cde4ed525ba77a90c976f5'
 snapshot=runner.budget_snapshot(runner.read_events(root/'data/attempt-ledger.jsonl'),runner.read_events(root/'data/gpu-healthcheck-ledger.jsonl'));assert snapshot==prior['budget_snapshot']
 review={'schema':'n34r9-prospective-runtime-inventory-review-v1','at':now,'source':s['source_commit'],'probe':ref(rt/'runtime-import-probe-v1.py'),'inventory':ref(rt/'runtime-import-probe-v1.json'),'candidate_closure':ref(rt/'runtime-closure.CANDIDATE-v1.json'),'strict_receipt':ref(rt/'runtime-probe-receipt-v1.json'),'probe_log':ref(rt/'probe.log'),'predecessor_closure':ref(out.parent/'000694/terminal-closure-v1.json'),'dino_checks':new['dino_checks'],'protobuf_checks':new['protobuf_checks'],'jit_checks':new['jit_checks'],'conversion_checks':new['conversion_checks'],'serialization_checks':new['serialization_checks'],'added_modules':added,'cpu_status':'PASS','controller_semantics':'PASS','cuda_initialized':False,'gpu_dispatched':False,'probe_exit_code':0,'root_cause':'The prior probe imported KeypointDetector without invoking its local Torch Hub entrypoint or lazy DINOv2 architecture imports. Loading hubconf through the installed Torch Hub loader and explicitly importing its vision_transformer dependency independently binds these source bytes. No native receipt was used to grant runtime trust; no model construction, weights, network or GPU were used.','scope':'CPU synthetic arrays, serialization, imports and frozen config composition only. No environment, model, GL context, GPU, provider, credentials or protected results. No benchmark edits.','native_runtime_completeness':'UNPROVEN_UNTIL_FRESH_AUDITED_EXECUTION','ledger_prefixes':prior['ledger_prefixes'],'budget_snapshot':snapshot,'old_charges_preserved':True,'release_enabled':False,'target_met':False,'next_action':next_action}
 write(out/'runtime-inventory-review-v1.json',review);binding=ref(out/'runtime-inventory-review-v1.json')
 for p in [root/'research-state.yaml',co/'checkpoint.json',co/'idea_tree.json']:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,c]:obj.update(n34r9_runtime_inventory_review=binding,status='N34R9_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',n34_continuation_status='N34R9_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',automatic_gpu_dispatch_authorized=False,next_action=next_action,updated_at=now)
 p=root/'research-state.yaml';t=p.with_suffix('.tmp');t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(p);write(co/'checkpoint.json',c)
 tree=json.loads((co/'idea_tree.json').read_text());tree['nodes']['15.4'].update(n34r9_runtime_inventory_review=binding,result='N34R8 invalid retained. Local Torch Hub entrypoint and lazy DINOv2 architecture imports plus retained CPU checks PASS; prospective lazy imports bound and strict runtime attestation/controller semantics PASS. N34R9 identity repair/release pending; native completeness and efficacy unproven.');write(co/'idea_tree.json',tree)
 print(json.dumps({'review':binding,'added_count':len(added),'added_modules':list(added),'next_action':next_action}))
