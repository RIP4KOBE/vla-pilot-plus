import json,hashlib,datetime,subprocess,sys,copy,fcntl,shutil
from pathlib import Path
import yaml
w=Path.cwd();sys.path.insert(0,str(w))
from scripts import qd_ed_final_runner as r, qd_ed_available_gpu_queue as q, qd_ed_n36_contract as c
base=w.parent/'autonomy_20261004';out=(base/'turns/001289').resolve()
def read(p):return json.loads(Path(p).read_text())
def ref(p):return {'path':str(Path(p).resolve()),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def verify(x):assert ref(x['path'])['sha256']==x['sha256'];return read(x['path'])
def write(p,v):
 t=Path(str(p)+'.tmp');t.write_text(json.dumps(v,indent=2)+'\n');t.replace(p)
now=datetime.datetime.now(datetime.timezone.utc);ds=read(base/'driver-status.json');assert ds['turn']==1289
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
for h in [ds['driver'],ds['process']]:
 a=Path(f'/proc/{h["pid"]}/stat').read_text().rsplit(')',1)[1].split();assert h['boot_id']==boot and int(a[19])==h['start_ticks'] and a[0]!='Z'
assert not (base/'STOP').exists() and not (base.resolve()/'STOP').exists() and now<datetime.datetime.fromisoformat(c.DEADLINE.replace('Z','+00:00'))
assert read(base/'turns/001288/receipt.json')['exit']==0
s=yaml.safe_load((w/'research-state.yaml').read_text());assert s.get('active_controller') is None and not s['current_owned_workers']
assert s['resource_isolation']['status']=='ACTIVE' and s['resource_isolation']['validation_status']=='PASS'
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert source==s['source_commit']=='30c6321715df86c5bab623db607bab2811aed56d'
authority=verify(s['n36r2_budget_authority']);verify(s['n36r2_independent_final_review']['report'])
ledgers={}
for name,x in authority['ledger_prefixes'].items():
 p=w/'data'/name;b=p.read_bytes();assert len(b)==x['bytes'] and hashlib.sha256(b).hexdigest()==x['sha256'];ledgers[name]={**ref(p),'bytes':len(b)}
events=r.read_events(w/'data/attempt-ledger.jsonl');resources=r.read_events(w/'data/gpu-healthcheck-ledger.jsonl');snap=r.budget_snapshot(events,resources)
assert snap['running']==snap['gpu_healthcheck_inflight']==0 and all(x[-1]['event'] in r.TERMINAL for x in r.event_groups(events).values())
prior_review=read(base/'turns/000915/probe-review-v1.json');assert prior_review['status']=='PASS';old=verify(prior_review['runtime']);terminal=verify(prior_review['terminal'])
draft=base/'turns/001282/final-source-refresh/runtime.isolated.draft-v1.json';runtime=read(draft)
assert q.same_mapping(old['gpu_mapping'],runtime['gpu_mapping'])
proof=q.reusable_probe(old,runtime['gpu_mapping'],resources,root=w);assert proof is not None
# Candidate flags are in memory until independent checks pass. They are not evidence.
candidate=copy.deepcopy(runtime);candidate.update(cuda_egl_verified=True,cuda_egl_probe=proof,provider_ready=True)
assert q.reusable_probe(candidate,candidate['gpu_mapping'],resources,root=w)==proof
env=r.child_environment(candidate);r.verify_provider(candidate,env,root=w);r.runtime_gpu(candidate,s)
admission=r.gpu_admission(physical_gpu=7,expected_uuid=candidate['gpu_mapping']['uuid'])
assert not (base/'STOP').exists() and not (base.resolve()/'STOP').exists()
write(out/'runtime.ready-v1.json',candidate)
review={'schema':'n36r2-root-runtime-readiness-v1','at':now.isoformat(),'status':'PASS_READINESS_ONLY_NOT_RELEASE','source':source,'runtime':ref(out/'runtime.ready-v1.json'),'disabled_runtime':ref(draft),'changed_fields':[k for k in candidate if candidate.get(k)!=runtime.get(k)],'accounting_authority':s['n36r2_budget_authority'],'reused_probe_review':ref(base/'turns/000915/probe-review-v1.json'),'reused_probe':proof,'probe_terminal':prior_review['terminal'],'verification':'Unmodified reusable_probe verified current probe code SHA, completed owning healthcheck charge, matching GPU mapping, evidence and rendered-frame hashes. Unmodified verify_provider verified CLI executable hash/version, official ChatGPT login, frozen skill metadata and sanitized environment. No credential files opened.','provider_model':candidate['frozen_stage_provider']['model'],'admission_observation':admission,'ledger_prefixes':ledgers,'new_gpu_seconds':0,'new_episode_dispatches':0,'new_provider_inference_calls':0,'runtime_closure_rebound':False,'release_enabled':False,'target_met':False,'limits':'Historical CUDA/EGL preparation proof is reusable under unchanged verifier. This is not N36 live arithmetic/controller/native audit evidence; RT-03/04 remain mandatory during actual metered execution.'}
write(out/'runtime-readiness-review-v1.json',review)
next_action='Use turn001289 runtime.ready-v1.json and hash-bound readiness review to update only readiness-dependent N36R2 bindings from accepted turn001282 package. Preserve isolated source routing and scientific rules; preparation.runtime_ready remains false until preparation is completed. Obtain external input-bound B5 review, freeze final plan omitting root_review/execution_release keys, external root production review and detached release before episode dispatch. Recheck live admission at launch; do not rebuild unchanged provenance.'
with open(w/'data/qd-ed-state.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 sp=w/'research-state.yaml';cp=w/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());checkpoint=read(cp);tree=read(tp)
 assert s.get('active_controller') is None and checkpoint.get('active_controller') is None
 for x in ledgers.values():assert ref(x['path'])['sha256']==x['sha256']
 for p in [sp,cp,tp]:shutil.copyfile(p,out/(p.name+'.before'))
 for obj in [s,checkpoint]:obj.update(n36r2_runtime_readiness=ref(out/'runtime-readiness-review-v1.json'),phase='N36R2_RUNTIME_READINESS_VERIFIED_RELEASE_PENDING',next_action=next_action,updated_at=now.isoformat())
 tree['nodes']['15.6'].update(n36r2_runtime_readiness=ref(out/'runtime-readiness-review-v1.json'),result='READINESS_VERIFIED_NO_GPU_RELEASE',score=None)
 tmp=sp.with_suffix('.tmp');tmp.write_text(yaml.safe_dump(s,sort_keys=False,allow_unicode=True));tmp.replace(sp);write(cp,checkpoint);write(tp,tree)
summary={'schema':'autonomy-bounded-operation-summary-v1','at':now.isoformat(),'source':source,'driver':ds['driver'],'coordinator':ds['process'],'live_handles':{},'active_controller':None,'ledger_prefixes':ledgers,'completed':'Reconciled normal prior exit, no live worker/controller and unchanged ledger. Verified reusable accounted CUDA/EGL proof and current official Codex ChatGPT login; froze readiness runtime only.','readiness_review':ref(out/'runtime-readiness-review-v1.json'),'next_action':next_action,'unresolved':['Rebound closure/controller/all40 manifests and detached release validation','RT-03/04 actual live native/controller/whole-episode audit evidence','Original validation/formal/required ablation evidence'],'target_met':False,'stop_present':False,'deadline':c.DEADLINE}
write(out/'operational-summary.json',summary)
(out/'operational-summary.md').write_text(f'Source {source}. Driver {ds["driver"]["pid"]} / coordinator {ds["process"]["pid"]} boot/start verified. No live GPU worker or experiment controller. Prior turn exited normally; ledger unchanged at 504 attempts.\n\nVerified reusable accounted GPU7 CUDA/EGL proof and current official Codex ChatGPT login; wrote runtime.ready-v1.json and hash-bound runtime-readiness-review-v1.json. No GPU execution, new charges, inference or release.\n\nNext: {next_action}\n\nOriginal validation/formal/ablation evidence and live audit obligations remain unresolved; goal not complete.\n')
(out/'operational-summary.sha256').write_text(ref(out/'operational-summary.json')['sha256']+'  operational-summary.json\n')
print(json.dumps({'review':ref(out/'runtime-readiness-review-v1.json'),'admission':admission,'next_action':next_action},indent=2))
