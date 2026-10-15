import json,pathlib,sys,hashlib,copy,datetime,traceback,yaml
owner=pathlib.Path.cwd();base=owner.parent/'autonomy_20261004';out=base/'turns/001597';plan=json.loads((out/'engineering-plan.frozen-v1.json').read_text());src=pathlib.Path(plan['worktree']);sys.path.insert(0,str(src))
from scripts import qd_ed_final_runner as r,qd_ed_available_gpu_queue as q

def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def verify(x):
 p=pathlib.Path(x['path']);assert ref(p)['sha256']==x['sha256'];return json.loads(p.read_text())
def put(name,d):
 p=out/name;assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');return ref(p)
result={'schema':'n36-engineering-readiness-verification-v2','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'disabled_runtime':plan['runtime'],'source':plan['source']['commit'],'new_gpu_seconds':0,'new_provider_inference_calls':0,'release_enabled':False,'checks':{}}
try:
 assert not (base/'STOP').exists();runtime=verify(plan['runtime']);state=yaml.safe_load((owner/'research-state.yaml').read_text());assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 for v in verify(plan['authority'])['ledger_prefixes'].values():assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
 metadata=q.current_metadata(7,root=src);result['metadata']=put('current-gpu-metadata-v1.json',metadata)
 assert q.same_mapping(metadata,runtime['gpu_mapping']);result['checks']['fresh_metadata_matches_frozen_mapping']='PASS'
 review=verify({'path':str(base/'turns/000915/probe-review-v1.json'),'sha256':'81fe322ac771f1e1a595bf9b2b5e8aeeb7a5f1b232d5b16bd451cdb5f9712ed8'});old=verify(review['runtime']);verify(review['terminal'])
 health=r.read_events(owner/'data/gpu-healthcheck-ledger.jsonl');proof=q.reusable_probe(old,metadata,health,root=src);assert proof is not None,'no reusable accounted matching-code GPU proof';result['checks']['accounted_gpu_preparation_proof']='PASS';result['reused_probe']=proof;result['reused_probe_review']=ref(base/'turns/000915/probe-review-v1.json')
 candidate=copy.deepcopy(runtime);candidate.update(metadata_mapping_verified=True,cuda_egl_verified=True,cuda_egl_probe=proof,provider_ready=True);candidate['gpu_mapping'].update(metadata_mapping_verified=True,cuda_egl_verified=True)
 assert q.reusable_probe(candidate,candidate['gpu_mapping'],health,root=src)==proof
 env=r.child_environment(candidate);r.verify_provider(candidate,env,root=src);result['checks']['current_official_codex_login']='PASS'
 r.runtime_gpu(candidate,state);result['admission_observation']=r.gpu_admission(physical_gpu=7,expected_uuid=candidate['gpu_mapping']['uuid'])
 assert not (base/'STOP').exists();assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(plan['deadline'].replace('Z','+00:00'))
 result.update(decision='PASS_PREPARATION_READINESS_ONLY',runtime=put('runtime.readiness-verified-v1.json',candidate),changed_fields=[k for k in candidate if candidate[k]!=runtime[k]],limits='Fresh metadata enumeration creates no GPU context. Historical accounted CUDA/EGL proof verified against current probe code and mapping; fresh metered engineering healthcheck remains mandatory. Preparation/release flags stay disabled and dependent bindings require refresh.')
except Exception as ex:result.update(decision='BLOCKED',error=str(ex),traceback=traceback.format_exc())
put('readiness-verification-v2.json',result);print(json.dumps(result))
