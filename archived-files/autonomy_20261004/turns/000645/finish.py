import pathlib,json,hashlib,datetime,sys,yaml,shutil
root=pathlib.Path.cwd();sys.path.insert(0,str(root));from scripts import qd_ed_final_runner as runner
out=(root.parent/'autonomy_20261004/turns/000645').resolve();d=out/'runtime-v1'
def ref(p):
 p=pathlib.Path(p).resolve();return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
entry=json.loads((out/'entry-reconciliation-v1.json').read_text())
for name,prefix in entry['ledger_prefixes'].items():
 b=(root/'data'/name).read_bytes();assert len(b)==prefix['bytes'] and hashlib.sha256(b).hexdigest()==prefix['sha256']
probe=json.loads((d/'runtime-import-probe-v1.json').read_text());closure=json.loads((d/'runtime-closure.CANDIDATE-v1.json').read_text());receipt=json.loads((d/'runtime-probe-receipt-v1.json').read_text())
assert not probe['errors'] and not probe['missing_files'] and not probe['uncovered_checkout_modules'] and not probe['cuda_initialized']
prior=json.loads((root.parent/'autonomy_20261004/turns/000639/runtime-v1/runtime-closure.CANDIDATE-v1.json').read_text())
added={k:v for k,v in closure['modules'].items() if k not in prior['modules']};changed={k:v for k,v in closure['modules'].items() if k in prior['modules'] and v!=prior['modules'][k]};removed=sorted(set(prior['modules'])-set(closure['modules']))
assert all(k in closure['modules'] for k in ['torch.utils.serialization','torch.utils.serialization.config'])
assert probe['serialization_checks']==[{'format':'zip','roundtrip':'PASS'},{'format':'legacy','roundtrip':'PASS'}]
next_action='Prepare isolated N34R4 recovery-identity repair through executor on existing production worktree, preserving N34R3 and all predecessor invalid records and scientific source. Use turn645 corrected CPU import inventory when regenerating runtime on the new adopted source. Freeze fresh finite accounting/protocol/30 manifests/root review/release; pass full public validation before any idle GPU7 admission. Do not replay N34R3 or weaken native audits.'
review={'schema':'n34r4-prospective-runtime-inventory-review-v1','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':entry['source'],'probe':ref(d/'runtime-import-probe-v1.py'),'inventory':ref(d/'runtime-import-probe-v1.json'),'candidate_closure':ref(d/'runtime-closure.CANDIDATE-v1.json'),'strict_receipt':ref(d/'runtime-probe-receipt-v1.json'),'serialization_checks':probe['serialization_checks'],'cpu_status':'PASS','controller_semantics':'PASS','cuda_initialized':False,'ordinary_module_count':len(closure['modules']),'checkout_module_count':len(probe['checkout_modules']),'added_modules':added,'changed_modules':changed,'removed_modules':removed,'dotenv_code_only':True,'scope':'Prospective CPU runtime inventory correction only; no loader, credential inspection, Main execution, model loading, environment construction, provider or GPU execution. No new manifests or dispatch. Candidate closure is not execution release.','old_charges_preserved':True,'scientific_source_unchanged':True,'native_runtime_completeness':'UNPROVEN_UNTIL_FRESH_AUDITED_EXECUTION','target_met':False,'next_action':next_action}
(out/'runtime-inventory-review-v1.json').write_text(json.dumps(review,indent=2)+'\n')
cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tree=cp.parent/'idea_tree.json';sp=root/'research-state.yaml'
with runner.locked(root/'data/qd-ed-state.lock'):
 s=runner.read_state(sp);c=json.loads(cp.read_text());t=json.loads(tree.read_text());assert s['active_controller'] is None and c['active_controller'] is None
 for p in [sp,cp,tree]:shutil.copyfile(p,out/(p.name+'.before'))
 for o in [s,c]:
  o.update(n34r4_runtime_inventory_review=ref(out/'runtime-inventory-review-v1.json'),next_action=next_action)
 n=t['nodes']['15.4'];n['n34r4_runtime_inventory_review']=ref(out/'runtime-inventory-review-v1.json');n['result']='N34R3 retained INVALID; prospective CPU import inventory correction passes exact runtime and controller checks. Fresh N34R4 identity/source/release still required; no scientific promotion.'
 for p,obj,is_yaml in [(sp,s,True),(cp,c,False),(tree,t,False)]:
  tmp=p.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(obj,sort_keys=False,allow_unicode=True) if is_yaml else json.dumps(obj,indent=2)+'\n');tmp.replace(p)
end={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':s['source_commit'],'ledger_prefixes':entry['ledger_prefixes'],'review':ref(out/'runtime-inventory-review-v1.json'),'active_controller':None,'driver_stop_present':(root.parent/'autonomy_20261004/STOP').exists(),'target_met':False,'next_action':next_action}
(out/'end-reconciliation-v1.json').write_text(json.dumps(end,indent=2)+'\n')
(out/'operational-summary.md').write_text(f'''Turn645 — {end['at']}

Current source {s['source_commit']}; scientific source71ffff1a0f70d9874b309db9ef1843c02bf17ebf unchanged. Bound handoff, exact authority, continuation and completion contract verified. Driver268073/start97715947 and coordinator709006/start135919793 verified on boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7; former controller666112 and worker669326 absent. Prior turn644 normal. STOP absent; deadline2026-10-11T11:13:13Z. No active GPU cohort.

Completed prospective CPU runtime inventory repair: tiny tensor ZIP and legacy serialization roundtrips PASS; strict runtime attestation and controller semantic proof PASS. Ordinary modules:{len(closure['modules'])}; checkout modules:{len(probe['checkout_modules'])}. No import errors, missing files or uncovered checkout modules; CUDA uninitialized. New ordinary modules:{list(added)}. Changed bindings:{list(changed)}. No removed modules:{removed}. This is candidate inventory, not an execution release. No new manifests, GPU dispatch, benchmark/source change, replay or retroactive acceptance.

Owning ledger prefixes unchanged;446 dispatches/63.6001770799448 GPUh, zero running; prior invalid charges, unknown telemetry and protected reserves retained. State/checkpoint and node15.4 bind runtime-inventory-review-v1.json. Only normal state lock used; driver locks untouched. Initial artifact-base lookup failed before probe creation/execution and was corrected; recorded in entry reconciliation.

Next bounded step: {next_action}

Unresolved: native runtime validity, matched Dev efficacy, scientific promotion, validation20/formal10/required ablations and hash-bound original-goal completion. Driver continues; no completion claim.
''')
print(json.dumps({'review':ref(out/'runtime-inventory-review-v1.json'),'added':list(added),'changed':list(changed),'removed':removed,'summary':str(out/'operational-summary.md')}))
