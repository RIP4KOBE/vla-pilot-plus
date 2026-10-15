import sys,os,pathlib,json,time,traceback
O=pathlib.Path(__file__).absolute().parent
root='/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/variants/n36_engineering_adapter_001482/implementation_worktree'
sys.path.insert(0,root);os.chdir(root)
from scripts import qd_ed_n36_bridge as b,qd_ed_n23_worker as w,qd_ed_n36_stop as stop
stop.check();plan=json.loads((O/'engineering-plan.draft-disabled-v1.json').read_text());audit=json.loads(pathlib.Path(plan['audit_plan']['path']).read_text());rows=[];start=time.monotonic()
for ref in list(audit['expected_manifests'].values())+[plan['engineering_manifest']]:
 stop.check();v=json.loads(pathlib.Path(ref['path']).read_text());config,resolved=b.compose_launch(v['argv'],plan['worktree'])
 # Production _verify_manifest_bound compares JSON round-tripped manifest to JSON artifact.
 normalized=json.loads(json.dumps(resolved));diff=[k for k in set(normalized)|set(v['resolved_config']) if normalized.get(k)!=v['resolved_config'].get(k)]
 row={'path':ref['path'],'row':v['row']['episode_key'],'composed_hash_matches':w.canonical_sha(config)==v['composed_config_sha256'],'json_roundtripped_resolved_matches':normalized==v['resolved_config'],'raw_python_resolved_matches':resolved==v['resolved_config'],'raw_type_difference_fields':[{'field':k,'python_type':type(resolved[k]).__name__,'json_type':type(v['resolved_config'][k]).__name__} for k in resolved if resolved[k]!=v['resolved_config'].get(k)],'remaining_difference_fields':diff}
 row['status']='PASS' if row['composed_hash_matches'] and row['json_roundtripped_resolved_matches'] else 'FAIL';rows.append(row)
 print(row['row'],row['status'],json.dumps(row['raw_type_difference_fields']),flush=True)
with (O/'config-recomposition-v1.json').open('x') as f:json.dump({'schema':'n36-json-config-recomposition-v1','expression':'w.canonical_sha(config)==stored hash and json.loads(json.dumps(resolved))==stored resolved config (same serialization as production _verify_manifest_bound)','results':rows,'status':'PASS' if all(r['status']=='PASS' for r in rows) else 'FAIL','elapsed_seconds':time.monotonic()-start,'does_not_supersede_full_manifest_helper_failures':True},f,indent=2)
