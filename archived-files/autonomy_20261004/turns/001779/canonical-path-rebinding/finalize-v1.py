import os,json,hashlib,subprocess
from pathlib import Path
O=Path(__file__).resolve().parent
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2])
def read(p):return json.loads(Path(p).read_text())
def rec(p):
 p=Path(p);v=p.read_bytes();return dict(path=str(p),bytes=len(v),sha256=hashlib.sha256(v).hexdigest())
def write(n,v):
 (O/n).write_text(json.dumps(v,indent=2,sort_keys=True)+'\n');return rec(O/n)
A=read(O/'authority-v1.json');R=read(O/'report-v1.json')
old=O.parent.parent/'001776/disabled-graph-composition/composition-v3'
rows=[]
for name in [f'audit-manifests/{i:02}.json' for i in range(40)]+['engineering-manifest.disabled-v1.json']:
 a=read(old/name);b=read(O/name)
 checks={k:a[k]==b[k] for k in ['argv','resolved_config','composed_config_sha256','row'] if k in a}
 assert all(checks.values()),name
 rows.append(dict(name=name,original=rec(old/name),current=rec(O/name),unchanged=checks))
plan=read(O/'engineering-plan.disabled-v1.json');audit=read(O/'all40-audit.immutable-disabled-v1.json')
oldplan=read(old/'engineering-plan.disabled-v1.json');oldaudit=read(old/'all40-audit.immutable-disabled-v1.json')
assert plan['stop_authority']==audit['stop_authority']==oldplan['stop_authority']==oldaudit['stop_authority']
assert set(A['stop_authority']['paths']) <= set(plan['stop_authority']['paths'])
assert all(not os.path.lexists(x) for x in set(A['stop_authority']['paths']+plan['stop_authority']['paths']))
assert plan['stop_authority']['deadline']==A['stop_authority']['deadline']
assert not any(os.path.lexists(x) for x in plan['stop_authority']['paths'])
for k in ('episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting'):assert audit[k]==oldaudit[k],k
spec=read(O/'specification.prospective-disabled-v1.json');review=read(A['root_scoped_review']['path']);oldspec=read(review['specification']['path'])
for k in spec:
 if k!='runtime_binding':assert spec[k]==oldspec[k],k
for k in spec['runtime_binding']:
 if k not in ('preparation','runtime_path','source_record_path'):assert spec['runtime_binding'][k]==oldspec['runtime_binding'][k],k
prior=read(A['prior_bindings']['path']);runtime=read(O/'disabled-runtime.json');oldruntime=read(prior['runtime']['path'])
oldruntime['preparation']['source_record']=runtime['preparation']['source_record'];assert runtime==oldruntime
assert read(O/'source-record.json')==read(prior['source_record']['path'])
closure=read(O/'runtime-closure.prospective-disabled-v1.json');oldclosure=read(prior['runtime_closure']['path']);oldclosure['runtime']=closure['runtime'];assert closure==oldclosure
assert all(x is False for x in plan['phase_authorization'].values()) and all(x is False for x in audit['phase_authorization'].values())
assert not runtime['preparation']['runtime_ready'] and not runtime['provider_ready'] and not runtime['cuda_egl_verified'] and not runtime['gpu_mapping']['cuda_egl_verified']
ledgers=[]
for r in A['ledger_prefixes'].values():
 actual=rec(r['path']);assert actual==r;ledgers.append(actual)
for r in read(O/'inputs-manifest-v1.json')['files']:assert rec(r['path'])==r
cmds=[]
for args in [['rev-parse','HEAD'],['diff','--name-only'],['diff','--cached','--name-only']]:
 p=subprocess.run(['git','--no-replace-objects','-C',A['worktree'],*args],text=True,capture_output=True,check=True)
 cmds.append(dict(argv=p.args,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
assert cmds[0]['stdout'].strip()==A['source'] and all(x['stdout']=='' for x in cmds[1:])
assert R['graph_complete'] and R['generated_audit_manifest_count']==40 and R['generated_engineering_manifest_count']==1
checks=read(O/'command-evidence-v1.json')['checks']
assert len([x for x in checks if x['check'].startswith('production audit manifest consumer ') and x['status']=='PASS'])==40
assert any(x['check']=='separate engineering manifest production consumer' and x['status']=='PASS' for x in checks)
preservation=write('scientific-ledger-preservation-v1.json',dict(schema='n36-canonical-rebinding-preservation-v1',manifest_checks=rows,ledger_files=ledgers,all_recorded_inputs_unchanged=True,source_commands=cmds,source_unchanged=True,prior_preservation=rec(O/'preservation-evidence-v1.json'),stop_authority=A['stop_authority'],approval_transferred=False,production_stop_binding=plan['stop_authority'],stop_bindings_byte_content_preserved=True,authority_stop_paths_subset_of_preserved_production_binding=True,supplemental_preservation_status='PASS',initial_preservation_diagnostic='Executor assertion compared authority duplicate lexical STOP paths with unchanged production lexical/canonical STOP paths. Original production bindings preserved exactly; both distinct production STOP locations checked absent. Authority duplicate remains untouched. No production validator changed.',scientific_specification_preserved=True,accounting_reserves_scope_preserved=True,runtime_only_source_record_rebound=True,closure_only_runtime_rebound=True))
R['blockers']=[x for x in R['blockers'] if x['check']!='science budget reserves original offsets journals and disabled authorization preservation']
R['preservation_diagnostic_resolution']='Initial executor STOP path equality assertion was overstrict; supplemental checks verify exact original production STOP binding and both distinct production STOP locations absent; supplied authority repeats the home path. Original command evidence retained.'
R['checks'].append(dict(check='supplemental exact scientific ledger and STOP preservation',status='PASS',evidence=preservation))
R.update(status='CANONICAL_PATH_REPAIRED_DISABLED_GRAPH_BLOCKED_CONTROLLER_REVIEW',preservation_evidence=preservation,exact_static_command_receipt=rec(O/'command-receipt-v1.json'),controller_review_status='PENDING_ROOT_REVIEW_OF_NEW_BINDINGS',canonical_runtime_path_repair_verified=True,all41_manifest_consumers_passed=True,independent_review_claimed=False)
R['limitations']=['All41 manifest consumers pass; verify_graph rejects the pending controller binding with reviewed controller semantics required. No approval was transferred to changed bindings.','Static disabled artifact repair only; no independent review, measurement, readiness, release, owning-state adoption or scientific success.']
write('report-v1.json',R)
(O/'report-v1.sha256').write_text(rec(O/'report-v1.json')['sha256']+'  report-v1.json\n')
# Reindex the final versions of this run only. Exclude wrappers owned by the caller and temporary caches.
known=read(O/'outputs-manifest-v1.json')['files']
paths={Path(x['path']) for x in known}
paths.update(O/x for x in ['finalize-v1.py','scientific-ledger-preservation-v1.json','command-receipt-v1.json','builder-stdout-v1.log'])
write('outputs-manifest-v1.json',dict(files=[rec(p) for p in sorted(paths)],excludes=['outputs-manifest-v1.json','artifact-manifest-v1.json','tmp/']))
paths.add(O/'outputs-manifest-v1.json');paths.add(O/'authority-v1.json')
write('artifact-manifest-v1.json',dict(schema='n36-canonical-path-rebinding-artifact-manifest-v1',files=[rec(p) for p in sorted(paths)],report=rec(O/'report-v1.json'),graph=rec(O/'graph.complete-disabled-v1.json'),excludes=['artifact-manifest-v1.json','tmp/','caller-owned wrapper/process files'],release_enabled=False,graph_verified=False,all41_manifest_consumers_passed=True))
print(json.dumps(dict(status=R['status'],blockers=R['blockers'],report=rec(O/'report-v1.json'))))
