import pathlib,json,hashlib,subprocess,datetime,os
O=pathlib.Path(__file__).absolute().parent
A=json.loads((O/'authority-v1.json').read_text())
def rec(p):
 p=pathlib.Path(p); h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(4*1024*1024),b''):h.update(chunk)
 return dict(path=str(p),bytes=p.stat().st_size,sha256=h.hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_text())
def save(n,v):
 raw=(json.dumps(v,indent=2,sort_keys=True,allow_nan=False)+'\n').encode()
 with (O/n).open('xb') as f:f.write(raw)
 return rec(O/n)
g=read(O/'generation-results-v1.json');checks=g['checks'];extra=read(O/'input-checks-v1.json') if (O/'input-checks-v1.json').exists() else {'checks':[]}
checks+=extra['checks']
p=read(O/'engineering-plan.draft-disabled-v1.json') if (O/'engineering-plan.draft-disabled-v1.json').exists() else None
preserved=[]
for r in g['inputs']:
 v=rec(r['path']);preserved.append(dict(reference=r,unchanged=v==r))
commands=list(g['commands'])
for argv in [['git','-C',A['source']['worktree'],'rev-parse','HEAD','HEAD^{tree}'],['git','-C',A['source']['worktree'],'diff','--name-only'],['git','-C',A['source']['worktree'],'diff','--cached','--name-only']]:
 q=subprocess.run(argv,capture_output=True,text=True,check=True);commands.append(dict(argv=argv,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr))
assert commands[-3]['stdout'].splitlines()==[A['source']['commit'],A['source']['tree']]
assert commands[-2]['stdout']==commands[-1]['stdout']==''
assert all(r['unchanged'] for r in preserved)
review=read(A['review']['path']);spec=read(review['active_records']['specification']['path']);pol=read(review['active_records']['policy']['path'])
paths={k:v for k,v in pol.items() if k.endswith('_path')};paths.update({k:spec['runtime_binding'][k] for k in ('runtime_path','source_record_path')})
presence={k:os.path.lexists(v) for k,v in paths.items()};assert all(v==(k in ('disabled_runtime_path','source_record_path')) for k,v in presence.items())
stops=[O.parents[2]/'STOP',pathlib.Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP')]
now=datetime.datetime.now(datetime.timezone.utc);veto=any(os.path.lexists(x) for x in stops) or now>=datetime.datetime.fromisoformat(A['deadline'].replace('Z','+00:00'))
pr=save('preservation-v1.json',dict(inputs=preserved,source=A['source'],tracked_clean=True,prospective_presence=presence,prospective_paths=paths,stop_paths=[str(x) for x in stops],stop_present=any(os.path.lexists(x) for x in stops),deadline=A['deadline'],checked_at=now.isoformat(),owner_state_checkpoint_tree_ledger_lock_writes=0,source_edits=0,poe_files_opened=False,protected_results_accessed=False,prohibited_design_accessed=False))
commands.insert(0,dict(argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(O/'prepare-graph-v1.py')],log=rec(O/'prepare-graph-v1.log')))
if (O/'input-checks-v1.json').exists():commands.append(dict(argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python','-B',str(O/'verify-inputs-v1.py')],log=rec(O/'verify-inputs-v1.log')))
cr=save('commands-v1.json',commands)
refs={}
if p:
 audit=read(p['audit_plan']['path']);runtime=read(p['runtime']['path'])
 refs=dict(source_record=rec(spec['runtime_binding']['source_record_path']),runtime=rec(p['runtime']['path']),engineering_plan=rec(O/'engineering-plan.draft-disabled-v1.json'),full40_audit=rec(p['audit_plan']['path']),full40_manifests={k:rec(v['path']) for k,v in audit['expected_manifests'].items()},separate_engineering_manifest=rec(p['engineering_manifest']['path']),bindings=rec(O/'bindings.disabled-v1.json'))
 for k in ('runtime_closure','controller_semantics','native_build','deployment','scope','accounting','scientific_equivalence'):refs[k]=rec(p[k]['path'])
 assert len(refs['full40_manifests'])==40
 assert p['authority'] is p['b5_review'] is None and p['frozen'] is p['release_enabled'] is False
 assert all(v is False for v in p['phase_authorization'].values())
 assert runtime['provider_ready'] is runtime['cuda_egl_verified'] is runtime['gpu_mapping']['cuda_egl_verified'] is runtime['preparation']['runtime_ready'] is False
 assert audit['dispatch_authority'] is audit['release_enabled'] is False and all(v is False for v in audit['phase_authorization'].values())
manifest=save('outputs-manifest-v1.json',dict(schema='n36-disabled-graph-outputs-v1',artifacts=[rec(v['path']) for v in g['outputs']],graph=refs,release_enabled=False))
fail=[c for c in checks if c['status']=='FAIL'];expected=[c for c in fail if c['check']=='complete disabled preparation graph' and 'reviewed controller semantics required' in c.get('message','')]
unexpected=[c for c in fail if c not in expected]
report=dict(schema='n36-disabled-graph-refresh-report-v1',at=now.isoformat(),decision='GENERATED_DISABLED_ROOT_ATTESTATION_PENDING' if p and not unexpected and not veto else 'BLOCKED_REQUIRES_BOUNDED_DISPOSITION',scope='Bounded inert CPU artifact generation from deployed source; not independent review or acceptance.',authority=rec(O/'authority-v1.json'),review=A['review'],source_placement=A['source_placement'],source=A['source'],active_records=review['active_records'],graph=refs,checks=checks,unexpected_failures=unexpected,commands=cr,preservation=pr,outputs_manifest=manifest,generation_evidence=rec(O/'generation-results-v1.json'),input_check_evidence=rec(O/'input-checks-v1.json'),executor_scripts=[rec(O/n) for n in ('prepare-graph-v1.py','verify-inputs-v1.py','finalize-report-v1.py')],implementation_references=[rec(O.parents[1]/n) for n in ('001682/disabled-graph-preparation/prepare-graph-v1.py','001682/disabled-graph-preparation/verify-inputs-v1.py','001691/refreshed-disabled-graph/refresh-result-v1.json')],elapsed_bound_seconds=1200,started_at='2026-10-11T00:12:44+00:00',finished_at=now.isoformat(),remaining_exact_gates=[
'Independent deployed-graph CPU review of the exact generated source/runtime/full40/separate engineering bindings.',
'Fresh detached owning-root controller binding attestation and controller evidence acceptance for d3225489f6edfd2e49f472dc1ea9307f14f8be70 and the new runtime/closure; proposals do not inherit old root acceptance.',
'Complete unmodified preparation.verify_graph must pass after accepted controller evidence is bound into a newly refreshed graph.',
'Exact preparation accounting authority with detached root review, dedicated owner preparation adoption, and separately reviewed finite preparation release.',
'Read-only exact deployed predispatch admission; missing measured readiness remains downstream and grants no measurement authority here.',
'Separately authorized live CUDA/EGL/provider proof with terminal mirrored accounting and external acceptance.',
'Ready-graph refresh, independent final B5, production protocol/source/accounting adoption, and distinct health/episode releases.'
],frozen_semantics=dict(engineering_plan=False,full_audit_view=True,explanation='The unchanged production validate_audit_view requires frozen=true solely for the immutable audit-only 40-row matrix. Dispatch/release/phases remain false. No executable plan was frozen; this explicit schema distinction is retained, not changed to bypass audit.'),effects=dict(source_edits=0,source_commits=0,owner_state_checkpoint_tree_ledger_lock_writes=0,gpu_calls=0,model_loads=0,native_builds=0,provider_preflight_calls=0,measurements=0,health_calls=0,episodes=0,agent_dispatches=0,cloud_calls=0,credential_reads=0,poe_files_opened=False,broad_tests_run=False),release_enabled=False,root_accepted=False,independently_reviewed=False,production_readiness=False,source_adopted=False,b5_review=None)
r=save('report-v1.json',report)
with (O/'report-v1.sha256').open('x') as f:f.write(r['sha256']+'  report-v1.json\n')
print(json.dumps(dict(decision=report['decision'],report=r,checks=[{k:c.get(k) for k in ('check','status','message')} for c in checks]),indent=2))
