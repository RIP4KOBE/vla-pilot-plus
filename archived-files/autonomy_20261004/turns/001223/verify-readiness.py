import json,hashlib,datetime,subprocess,sys,copy,fcntl
from pathlib import Path
import yaml
w=Path.cwd();sys.path.insert(0,str(w))
from scripts import qd_ed_final_runner as r, qd_ed_available_gpu_queue as q, qd_ed_n36_contract as c
base=w.parent/'autonomy_20261004';out=(base/'turns/001223').resolve()
def read(p):return json.loads(Path(p).read_text())
def ref(p):return {'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def verify(x):assert ref(x['path'])['sha256']==x['sha256'];return read(x['path'])
def write(p,v):
 t=Path(str(p)+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(base/'driver-status.json');assert ds['turn']==1223
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 a=Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(a[19])==h['start_ticks'] and a[0]!='Z'
assert not (base/'STOP').exists() and now<datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
s=yaml.safe_load((w/'research-state.yaml').read_text());assert s.get('active_controller') is None and not s['current_owned_workers']
assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==s['source_commit']=='066f2bf57e05111fea329ff7c393ac3e002d7c0f'
authority=verify(s['n36r1_budget_authority']);ledgers={}
for name,x in authority['ledger_prefixes'].items():
 p=w/'data'/name;b=p.read_bytes();assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'];ledgers[name]={**ref(p),'bytes':len(b)}
events=r.read_events(w/'data/attempt-ledger.jsonl');resources=r.read_events(w/'data/gpu-healthcheck-ledger.jsonl');snap=r.budget_snapshot(events,resources)
assert snap['running']==snap['gpu_healthcheck_inflight']==0 and all(x[-1]['event'] in r.TERMINAL for x in r.event_groups(events).values())
prior_review=read(base/'turns/000915/probe-review-v1.json');assert prior_review['status']=='PASS';old=verify(prior_review['runtime']);verify(prior_review['terminal'])
draft=base/'turns/001219/runtime-input-repair/cpu-v1/runtime-candidate-v1/runtime.disabled-candidate.json';runtime=read(draft)
assert q.same_mapping(old['gpu_mapping'],runtime['gpu_mapping'])
# Disabled CPU candidate intentionally clears metadata/readiness flags. Restore only
# from its hash-bound metadata file and accepted accounted proof, never from a flag alone.
metadata_path=Path(runtime['egl_device_metadata_path']);metadata=read(metadata_path)
records=[x for x in runtime['files'] if x['path']==str(metadata_path)];assert len(records)==1
assert ref(metadata_path)['sha256']==records[0]['sha256'] and metadata_path.stat().st_size==records[0]['size_bytes']
assert metadata['metadata_mapping_verified'] is True
assert all(metadata.get(k)==v for k,v in runtime['gpu_mapping'].items() if k not in ['cuda_egl_verified','metadata_mapping_verified'])
proof=q.reusable_probe(old,metadata,resources,root=w);assert proof
candidate=q.clone_runtime(runtime,metadata,metadata_path,proof);candidate['provider_ready']=True
assert q.reusable_probe(candidate,candidate['gpu_mapping'],resources,root=w)==proof
assert candidate['frozen_stage_provider']['backend']=='codex_cli' and candidate['frozen_stage_provider']['model']=='gpt-6-astra'
env=r.child_environment(candidate);r.verify_provider(candidate,env,root=w);r.runtime_gpu(candidate,s)
admission=r.gpu_admission(physical_gpu=7,expected_uuid=candidate['gpu_mapping']['uuid'])
assert not (base/'STOP').exists()
for x in ledgers.values():assert ref(x['path'])['sha256']==x['sha256']
write(out/'runtime.ready-v1.json',candidate)
review={'schema':'n36-root-runtime-readiness-v1','at':now.isoformat(),'status':'PASS_READINESS_ONLY_NOT_RELEASE','source':source,'runtime':ref(out/'runtime.ready-v1.json'),'disabled_runtime':ref(draft),'changed_fields':[k for k in runtime if candidate.get(k)!=runtime[k]],'accounting_authority':s['n36r1_budget_authority'],'reused_probe_review':ref(base/'turns/000915/probe-review-v1.json'),'reused_probe':proof,'probe_terminal':prior_review['terminal'],'verification':'Unmodified reusable_probe checked current probe code SHA, owning completed healthcheck charge, GPU mapping, evidence and rendered-frame hashes. Unmodified verify_provider checked CLI executable hash/version, current official ChatGPT login, frozen skill metadata and sanitized environment. No credential files opened.','provider_model':candidate['frozen_stage_provider']['model'],'admission_observation':admission,'ledger_prefixes':ledgers,'new_gpu_seconds':0,'new_episode_dispatches':0,'new_provider_inference_calls':0,'runtime_closure_rebound':False,'release_enabled':False,'target_met':False,'retained_initial_check_failure':'Disabled candidate cleared metadata_mapping_verified; first reusable_probe check returned None and stopped before writes. Second conservative exact-dictionary comparison rejected the intentionally compact mapping; every existing non-readiness mapping field was then checked against the full bound metadata. Restored mapping only from SHA/size-verified bound metadata and revalidated existing proof without weakening verifier.', 'limits':'Reusable historical CUDA/EGL preparation evidence only. N36R1 live arithmetic/controller/native audit and RT-03/04 still mandatory. Production reviewer running; this is not a release.'}
write(out/'runtime-readiness-review-v1.json',review)
with (w/'data/qd-ed-state.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX);sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());checkpoint=read(cp);tree=read(tp)
 for obj in [s,checkpoint]:obj.update(n36r1_runtime_readiness=ref(out/'runtime-readiness-review-v1.json'),updated_at=now.isoformat())
 tree['nodes']['15.6']['runtime_readiness']=ref(out/'runtime-readiness-review-v1.json')
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,checkpoint);write(tp,tree)
print(json.dumps({'review':ref(out/'runtime-readiness-review-v1.json'),'admission':admission,'new_gpu_seconds':0}))
