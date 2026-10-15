import json,hashlib,shlex,datetime
from pathlib import Path
O=Path(__file__).resolve().parent
H=lambda b:hashlib.sha256(b).hexdigest()
def ref(p):
 p=Path(p).resolve();return dict(path=str(p),sha256=H(p.read_bytes()))
def read(p):return json.loads(Path(p).read_text())
def save(n,d):
 with (O/n).open('x') as f:json.dump(d,f,indent=2,sort_keys=True)
 return ref(O/n)
g=read(O/'graph.complete-disabled-v1.json');inputs=read(O/'release-inputs.disabled-v1.json');spec=read(g['specification']['path']);policy=read(g['policy']['path']);checks=[]
def chk(label,r):
 p=Path(r['path']);checks.append(dict(field=label,reference=r,absolute=p.is_absolute(),canonical=str(p.resolve())==str(p),hash_matches=H(p.read_bytes())==r['sha256']))
for k in ['specification','source_record','baseline']:chk('release.'+k,inputs[k])
for k,r in inputs['graph'].items():chk('release.graph.'+k,r)
for k,r in g.items():
 if isinstance(r,dict) and set(r)>={'path','sha256'}:chk('graph.'+k,r)
# Verify each generated manifest, scope/accounting and changed operational dependency.
plan=read(g['plan']['path'])
for k in ['scope','accounting','audit_plan','engineering_manifest','runtime','runtime_closure','controller_semantics']:chk('plan.'+k,plan[k])
audit=read(g['audit']['path'])
for k,r in audit['expected_manifests'].items():chk('audit.expected_manifests.'+k,r)
for k in ['preparation','amendment']:chk('specification.runtime_binding.'+k,spec['runtime_binding'][k])
legacy=[]
def walk(v,field):
 if isinstance(v,dict):
  if isinstance(v.get('path'),str) and v['path'].startswith('/') and str(Path(v['path']).resolve())!=v['path']:
   legacy.append(dict(field=field,reference=v,resolved_path=str(Path(v['path']).resolve()),reason='Inherited historical pin retained; no recursive provenance rewrite or source audit weakening authorized'))
  for k,x in v.items():walk(x,field+'.'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):walk(x,field+'.'+str(i))
walk(spec,'specification')
paths={k:v for k,v in policy.items() if k.endswith('_path')};paths['runtime_output_path']=spec['runtime_binding']['runtime_path']
assert all(Path(v).is_absolute() and str(Path(v).resolve())==v and Path(v).is_relative_to(O) for v in paths.values())
assert len(set(paths.values()))==len(paths)
assert all(not Path(v).exists() for k,v in paths.items() if k!='disabled_runtime_path')
struct=save('structural-integrity-report-v1.json',dict(schema='n36-canonical-successor-structural-integrity-v1',status='BLOCKED_BROAD_CANONICAL_CLOSURE',direct_operational_reference_checks_status='PASS' if all(c['absolute'] and c['canonical'] and c['hash_matches'] for c in checks) else 'FAIL',checks=checks,scientific_payloads=ref(O/'scientific-payload-integrity-v1.json'),fresh_destinations=paths,fresh_destinations_status='PASS',inherited_specification_noncanonical_references=legacy,all_external_and_embedded_paths_canonical=False,recursive_provenance_rebuilt=False,full_production_audit_run=False,production_preflight=ref(O/'production-preflight-result-v1.json')))
argv=['timeout','--signal=TERM','--kill-after=5s','600s','/home/hynx/miniconda3/envs/vla-pilot/bin/python3.12','-B',str(O/'strict-production-admission-v1.py')]
command=shlex.join(argv)
cmdref=save('next-strict-production-admission-command-v1.json',dict(cwd=g['actual_source_worktree'],argv=argv,shell_command=command,script=ref(O/'strict-production-admission-v1.py'),graph=ref(O/'graph.complete-disabled-v1.json'),specification=g['specification'],CPU_only=True,measurement_authorized=False,expected_current_outcome='BLOCKED at pending recovery review; no full graph PASS claimed',after_review='Authentic owner-reviewed successor dependencies require a fresh graph and corresponding command binding; do not mutate this frozen candidate.',deadline='2026-10-11T11:13:13Z',managed_timeout_seconds=600))
prov=read(O/'provenance-reconciliation-v1.json')
report=save('report-final-v1.json',dict(schema='n36-bounded-canonical-successor-report-v1',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),node_id='15.6',role='bounded CPU operational artifact executor',status='DISABLED_COMPOSITION_COMPLETE_ADMISSION_BLOCKED',resource_id=g['resource_id'],source_commit='808e27f702564fe51db45016e139b68ecb476f8c',owner_worktree=prov['owner_worktree'],output_directory=str(O),authority=ref(O/'authority-v1.json'),graph=ref(O/'graph.complete-disabled-v1.json'),release_inputs=ref(O/'release-inputs.disabled-v1.json'),provenance=ref(O/'provenance-reconciliation-v1.json'),structural_integrity=struct,scientific_payload_integrity=ref(O/'scientific-payload-integrity-v1.json'),production_preflight=ref(O/'production-preflight-result-v1.json'),next_strict_production_admission=cmdref,exact_next_command=command,retained_predecessors=5,retained_preparation_gpu_seconds=prov['retained_preparation_seconds'],retained_provider_calls=prov['retained_provider_calls'],blockers=['Five-predecessor recovery contract requires authentic owner terminal reconciliation and accepted review; production rejects null reference.','Changed runtime and closure bindings require controller review; production rejects PENDING_OWNER_REVIEW.','Broad canonical closure cannot be claimed: eight inherited specification reference paths use symlinked ancestors. Accepted source policy literally pins historical repair authority and immutable scientific/accounting specification; rewriting these within this bounded source-unchanged task would violate production policy.','Full strict production graph admission has not run; exact bounded CPU command supplied. Finite budget admission and independent release review remain pending.'],production_policy_check='PASS',full_audit_status='NOT_RUN',canonical_direct_release_inputs='PASS',canonical_entire_embedded_closure='BLOCKED',scientific_payloads_unchanged=41,source_edits=False,git_edits=False,old_artifact_edits=False,state_checkpoint_tree_ledger_edits=False,measurement_run=False,GPU_used=False,provider_calls=0,episodes_run=0,release_enabled=False,readiness_accepted=False,target_met=False))
text='Disabled successor composition completed for n36_readiness_preparation_recovery_001876. All 41 scientific payloads unchanged; direct release input canonical paths and hashes verified. Admission remains BLOCKED on recovery/controller reviews and eight inherited noncanonical specification pins. No full audit PASS claimed; no GPU/provider/measurement/source/state/ledger changes. Report: '+str(O/'report-final-v1.json')+' (sha256 '+report['sha256']+'). Exact next bounded strict CPU admission command: '+command+'\n'
(O/'last-message').write_text(text);(O/'last-message.txt').write_text(text)
print(json.dumps(dict(report=report,structural_integrity=struct,next_command=cmdref,checks=len(checks),inherited_noncanonical_specification_pins=len(legacy))))
