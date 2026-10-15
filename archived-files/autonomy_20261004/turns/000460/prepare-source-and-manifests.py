import sys,json,pathlib,hashlib,subprocess,datetime
root=pathlib.Path.cwd(); sys.path.insert(0,str(root))
from scripts import qd_ed_n23_worker as w, qd_ed_n32r3_bridge as b, qd_ed_n32r3_contract as c, qd_ed_n32r3_release as rel, qd_ed_n32r3_prepare as prep
from scripts.qd_ed_n32r3_history import validate_mapping
base=root.parent; turn=base/'autonomy_20261004/turns/000460'; v=base/'variants/n32_archive_eligible_capture'; out=v/'root-continuation-release-v3'
assert not (base/'autonomy_20261004/STOP').exists()
assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-10-11T11:13:13+00:00')
assert not out.exists()
candidate=json.loads((v/'prospective-continuation-v3/plan-candidate-v1.json').read_text())
parent_ref=candidate['parent_plan']; parent=c.read_ref(parent_ref)
release_ref=c.ref(v/'root-recovery-release-v2/execution-release-v1.json'); released=c.read_ref(release_ref)
source=w.source_record(root,b.source_paths(root)); assert source['commit']=='36aac818c8ea0ec3ce18413e678963818bb5bb5d'
changed=subprocess.check_output(['git','diff','--name-only',c.BASE_SOURCE,source['commit'],'--'],text=True).splitlines()
plan={**parent,'schema':'n32r3-composition-input-v1','frozen':False,'release_enabled':False,'phase_authorization':{'dev':False,'validation':False,'formal':False},'source':source,'scientific_source':parent['source'],'parent_plan':parent_ref,'parent_release':release_ref,'parent_review':released['root_review'],'carry_forward_map':candidate['carry_forward_map'],'command_candidates':candidate['command_candidates'],'preparation_review':c.ref(base/'autonomy_20261004/turns/000449/preparation-root-review.json'),'episodes':c.expected_rows(root),'limits':c.LIMITS,'worker_contract':c.WORKER_CONTRACT,'expected_manifests':{},'artifact_root':candidate['artifact_root_candidate']}
# Remove inherited approvals: this document is composition input only.
for key in ('authority','protocol'): plan.pop(key)
idx={x['path']:x['sha256'] for x in source['files']}
att={'schema':'n32r3-source-continuity-review-v1','approved':True,'parent_plan':parent_ref,'parent_release':release_ref,'carry_forward_map':plan['carry_forward_map'],'command_candidates':plan['command_candidates'],'scientific_source':parent['source'],'operational_source':source,'changed_files':{p:idx[p] for p in sorted(changed)},'scientific_changes':[],'audit_changes':[],'shared_routing':['scripts/qd_ed_final_runner.py']}
w.atomic_json(out/'operational-source-v1.json',source)
w.atomic_json(out/'source-continuity-review-v1.json',att)
plan['source_continuity']=c.ref(out/'source-continuity-review-v1.json')
rel.verify_continuity(plan); validate_mapping(plan)
w.atomic_json(out/'composition-input-v1.json',plan)
refs=prep.compose(c.ref(out/'composition-input-v1.json'),pathlib.Path(plan['artifact_root'])/'manifests-v1')
result={'schema':'n32r3-root-composition-review-v1','status':'SOURCE_CONTINUITY_AND_16_MANIFESTS_PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'composition_input':c.ref(out/'composition-input-v1.json'),'source_continuity':plan['source_continuity'],'manifest_index':c.ref(pathlib.Path(plan['artifact_root'])/'manifests-v1/manifest-index.json'),'manifest_count':len(refs),'source_files':len(source['files']),'changed_files':changed,'gpu_dispatched':False,'production_release_approved':False,'next_step':'Prospective accounting/protocol adoption, full runtime admission and detached production release review.'}
w.atomic_json(turn/'composition-review.json',result)
print(json.dumps(result,indent=2))
