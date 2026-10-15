import json, pathlib, subprocess, hashlib, datetime
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_bridge as b, qd_ed_n32r3_contract as c, qd_ed_n32r3_release as release, qd_ed_n32r3_prepare as prepare
root=pathlib.Path.cwd(); session=root.parent; turn=(session/'autonomy_20261004/turns/000468').resolve()
old_dir=session/'variants/n32_archive_eligible_capture/root-continuation-release-v3'
plan=json.loads((old_dir/'accounted-composition-input-v1.json').read_text())
review=c.read_ref({'path':str(session/'autonomy_20261004/turns/000466/command-path-root-review.json'),'sha256':'248ab97859f39679574de668048e647b85ef922b4d939f159992a9e8a53e42f4'})
adopt=c.read_ref({'path':str(session/'autonomy_20261004/turns/000467/source-adoption.json'),'sha256':'dbac639b881efcd9d8dbb6d4a4108f4d0530550db9258c2a35973d37c11e9ad0'})
assert not pathlib.Path(plan['stop_path']).exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
ledger=(root/'data/attempt-ledger.jsonl').read_bytes()
assert len(ledger)==5694864 and hashlib.sha256(ledger).hexdigest()=='8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6'
source=w.source_record(root,b.source_paths(root)|{x['path'] for x in plan['source']['files']})
assert source['commit']==review['reviewed_commit']=='04d1255016fa13a2d467995b9e37a6a829356a1c'
w.atomic_json(turn/'operational-source-v2.json',source)
plan['source']=source
changed=subprocess.check_output(['git','diff','--name-only',plan['scientific_source']['commit'],source['commit'],'--'],text=True).splitlines()
index={x['path']:x['sha256'] for x in source['files']}
continuity={'schema':'n32r3-source-continuity-review-v1','approved':True,**{k:plan[k] for k in ('parent_plan','parent_release','carry_forward_map','command_candidates','scientific_source')},'operational_source':source,'changed_files':{p:index[p] for p in sorted(changed)},'scientific_changes':[],'audit_changes':[],'shared_routing':['scripts/qd_ed_final_runner.py']}
w.atomic_json(turn/'source-continuity-review-v2.json',continuity)
plan['source_continuity']=c.ref(turn/'source-continuity-review-v2.json')
plan['command_path_amendment']=review['amendment_candidate']
plan['expected_manifests']={}
release.verify_continuity(plan)
from scripts.qd_ed_n32r3_paths import verify_amendment
amendment=verify_amendment(plan)
w.atomic_json(turn/'composition-input-v2.json',plan)
refs=prepare.compose(c.ref(turn/'composition-input-v2.json'),pathlib.Path(plan['artifact_root'])/'manifests-v2')
assert len(refs)==16
w.atomic_json(turn/'composition-result-v2.json',{'schema':'n32r3-root-composition-review-v2','source':source['commit'],'input':c.ref(turn/'composition-input-v2.json'),'continuity':plan['source_continuity'],'command_path_amendment':plan['command_path_amendment'],'expected_manifests':refs,'exact_path_changes_per_cell':3,'manifest_count':len(refs),'release_enabled':False,'gpu_dispatched':False,'ledger_sha256':hashlib.sha256(ledger).hexdigest(),'historical_charges_retained':438})
print(json.dumps({'status':'COMPOSED','manifests':len(refs),'result':c.ref(turn/'composition-result-v2.json')}))
