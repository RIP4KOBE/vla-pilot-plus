import pathlib,json,sys,hashlib,datetime,shutil,subprocess,yaml
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000716').resolve();rt=out/'runtime-v1';co=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(p,d):
 t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
prior=json.loads((out.parent/'000715/terminal-closure-v1.json').read_text())
for name,v in prior['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==v['bytes'] and hashlib.sha256(b).hexdigest()==v['sha256']
new=json.loads((rt/'runtime-import-probe-v1.json').read_text());old=json.loads((out.parent/'000705/runtime-v1/runtime-import-probe-v1.json').read_text())
assert not new['errors'] and not new['uncovered_checkout_modules'] and not new['missing_files'] and not new['cuda_initialized']
assert len(new['jit_checks'])==6 and all(x['status']=='PASS' for x in new['jit_checks'])
log=(rt/'probe.log').read_text();assert '"runtime_attestation": "PASS"' in log and '"controller_proof": "PASS"' in log
added={k:v for k,v in new['external_modules'].items() if k not in old['external_modules']}
assert 'imageio.plugins.pillow' in added and all(x['status']=='PASS' for x in new['pillow_checks'])
assert new['protobuf_checks'][0]['synthetic_model_roundtrip']=='PASS'
next_action='Prepare isolated N34R11 recovery identity through executor, retaining all eleven N34 invalid charges. Regenerate runtime closure and fresh manifests with turn716 combined qualitative-image/video output probe on adopted source. Freeze exact prospective accounting, protocol and independently reviewed release before GPU7 admission. No replay, weakened audit or protected evaluation.'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(root/'research-state.yaml');c=json.loads((co/'checkpoint.json').read_text());assert s['active_controller'] is None and c['active_controller'] is None
 assert s['source_commit']==subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()=='1151333e4cca32376afa2252e57a142411011f9b'
 snapshot=runner.budget_snapshot(runner.read_events(root/'data/attempt-ledger.jsonl'),runner.read_events(root/'data/gpu-healthcheck-ledger.jsonl'));assert snapshot==prior['budget_snapshot']
 review={'schema':'n34r11-prospective-runtime-inventory-review-v1','at':now,'source':s['source_commit'],'probe':ref(rt/'runtime-import-probe-v1.py'),'inventory':ref(rt/'runtime-import-probe-v1.json'),'candidate_closure':ref(rt/'runtime-closure.CANDIDATE-v1.json'),'strict_receipt':ref(rt/'runtime-probe-receipt-v1.json'),'probe_log':ref(rt/'probe.log'),'predecessor_closure':ref(out.parent/'000715/terminal-closure-v1.json'),'video_checks':new['video_checks'],'pillow_checks':new['pillow_checks'],'audit_primitive_checks':new['audit_primitive_checks'],'dino_checks':new['dino_checks'],'protobuf_checks':new['protobuf_checks'],'jit_checks':new['jit_checks'],'conversion_checks':new['conversion_checks'],'serialization_checks':new['serialization_checks'],'added_modules':added,'cpu_status':'PASS','controller_semantics':'PASS','cuda_initialized':False,'gpu_dispatched':False,'probe_exit_code':0,'root_cause':'The video-only synthetic probe succeeded at writing and decoding MP4 but did not load imageio.plugins.pillow; its failed assertion and log are retained. Production utils.eds_eval_vis.save_image uses imageio.imwrite. Executing save_image and save_side_by_side with synthetic PNG arrays independently loads the missing plugin before inventory capture. Combined output paths, retained imports, strict runtime receipt and controller semantics pass. Native end-to-end completeness remains unproven.','scope':'CPU synthetic arrays, serialization, imports and frozen config composition only. No environment, model, GL context, GPU, provider, credentials or protected results. No benchmark edits.','native_runtime_completeness':'UNPROVEN_UNTIL_FRESH_AUDITED_EXECUTION','ledger_prefixes':prior['ledger_prefixes'],'budget_snapshot':snapshot,'old_charges_preserved':True,'release_enabled':False,'target_met':False,'next_action':next_action}
 write(out/'runtime-inventory-review-v1.json',review);binding=ref(out/'runtime-inventory-review-v1.json')
 for p in [root/'research-state.yaml',co/'checkpoint.json',co/'idea_tree.json']:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,c]:obj.update(n34r11_runtime_inventory_review=binding,status='N34R11_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',n34_continuation_status='N34R11_CPU_RUNTIME_INVENTORY_PASS_IDENTITY_REPAIR_PENDING',automatic_gpu_dispatch_authorized=False,next_action=next_action,updated_at=now)
 p=root/'research-state.yaml';t=p.with_suffix('.tmp');t.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));t.replace(p);write(co/'checkpoint.json',c)
 tree=json.loads((co/'idea_tree.json').read_text());tree['nodes']['15.4'].update(n34r11_runtime_inventory_review=binding,result='N34R10 invalid retained. Synthetic qualitative-image/video output and retained import checks PASS; strict runtime attestation/controller semantics PASS. Full native audit remains unproven. N34R11 identity repair/release pending; native completeness and efficacy unproven.');write(co/'idea_tree.json',tree)
 print(json.dumps({'review':binding,'added_count':len(added),'added_modules':list(added),'next_action':next_action}))
