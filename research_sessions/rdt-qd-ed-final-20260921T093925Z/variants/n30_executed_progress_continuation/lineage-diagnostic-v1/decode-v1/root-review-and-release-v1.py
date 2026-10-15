"""Root source review and finite release for one existing-evidence CPU diagnosis."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
B=Path(__file__).resolve().parent;D=B.parent;W=D.parent.parents[1]/'study_worktree'
T=time.process_time();reads=[]
def read(p,sha=None):
 p=Path(p);assert p.suffix in {'.json','.md','.py'};b=p.read_bytes();assert len(b)<8*1024**2
 h=hashlib.sha256(b).hexdigest();reads.append({'path':str(p),'bytes':len(b),'sha256':h})
 if sha:assert h==sha,(str(p),h)
 return b
def j(p,sha=None):return json.loads(read(p,sha))
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(read(p)).hexdigest()}
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
delivery=j(B/'delivery-manifest-v1.json','8fd998be9ea291214e27a3f2f6b061a9f5e652f217cfe2627b07db512c1033cc')
for x in delivery['files']:read(x['path'],x['sha256'])
manifest=j(B/'decoder-source-manifest-v1.json','7905260c9cac6c2c3fae0814392d33909f30d78fefa724533d598c2cdabc6fe8')
reader=read(manifest['reader']['path'],'3f6404a29c0108f190a5eb83dffbfb0e42696f1cef1be44d9612c5c4dc99263d').decode()
for x in manifest['scientific_source_files']:assert len(read(x['path'],x['sha256']))==x['bytes']
command=j(B/'command.disabled.v1.json')
release=j(B/'execution-release.disabled.v1.json')
assert release['executable'] is False and command['executable'] is False
assert release['reader']==manifest['reader'] and release['limits']['containers']==34 and release['limits']['container_bytes']==24273690
for key in ('input_bindings','protocol','phase_a_review','source_manifest'):read(release[key]['path'],release[key]['sha256'])
for name in command['expected_output_names']:assert not (B/name).exists(),name
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review={'schema':'n30-lineage-root-decoder-review-v1','at':now,'decision':'ACCEPT_FOR_ONE_CPU_DIAGNOSTIC',
 'reader':manifest['reader'],'source_manifest':ref(B/'decoder-source-manifest-v1.json'),'delivery':ref(B/'delivery-manifest-v1.json'),
 'phase_a_review':release['phase_a_review'],'command':ref(B/'command.disabled.v1.json'),
 'checks':['full standalone reader manually reviewed; no production/model/scorer/RBF/native auditor imports or calls',
 'copy/mask/canonical/source-pool/identity-parent-row schedule/final archive/decode/commit/actual feedback matches frozen source structure',
 'added event reset, Main packet/tracker/current target, guidance stage, commit step and offspring lane-order checks reviewed',
 'exact34 payload whitelist installed before Torch import, one filesystem read and one weights_only CPU load per file',
 'whole-container co-resident tensor decoding disclosed; only whitelisted fields analyzed; no reward/provider body/geometry rescoring',
 '120s external timeout and CPU limit,16GiB AS before Torch,2threads/affinity0,1,CUDA hidden,128MiB ZIP/storage caps',
 'duplicate contents remain ambiguous; unique content inference is not original archive provenance or total causal influence'],
 'documentation_correction':'preparation report said per-round/per-step partial; actual code persists per-container load progress and only completed-episode partial. Incomplete current episode may have no analysis output. This does not authorize retry.',
 'runtime_limits':'Python audit guard is not kernel sandbox; native loader probes may not be recorded. torch CUDA initialization observed, no driver-probe absence claim.',
 'root_tensor_read_decode_count':0,'root_numerical_replay_count':0,'runtime_compatibility_unproven_before_execution':True,
 'cpu_seconds':time.process_time()-T,'reads':reads,'scientific_candidate_nominated':False,'target_met':False}
write(B/'root-decoder-review-v1.json',review)
release.update(executable=True,payload_read_authorized_now=True,requires_root_review_and_new_release=False,
 root_review=ref(B/'root-decoder-review-v1.json'),command=ref(B/'command.disabled.v1.json'),released_at=now,
 authority='Existing user-authorized routine CPU diagnostics within original Arbor task; no extra simulator transitions or GPU run.',
 execution_count=1,whole_container_decode_authorized=True,analyze_only_protocol_fields=True,automatic_retry_authorized=False,
 gpu_api_model_simulator_authorized=False,protected_phase_access_authorized=False,budget_change_authorized=False)
write(B/'root-execution-release-v1.json',release)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['active_iteration'] is None and state['active_controller'] is None and state['current_owned_workers']==[]
 assert state['current_cpu_task']['phase']=='N30_LINEAGE_DECODER_PREPARATION'
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 snap=B/'execution-registration-before-v1';snap.mkdir(exist_ok=False)
 for name,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(name+'.json'),obj)
 previous=copy.deepcopy(state['current_cpu_task']);previous.update(status='COMPLETE_PREPARATION_ONLY',closed_at=now,review=ref(B/'root-decoder-review-v1.json'))
 state.setdefault('closed_cpu_tasks',{})['N30_LINEAGE_DECODER_PREPARATION']=previous
 task={'status':'DISPATCHED','phase':'N30_FIRST_ACTIVE_LINEAGE_CPU_DECODE','node_id':'14.1','agent':'/root/n22_cpu_executor',
 'source_base':release['source_commit'],'reader':release['reader'],'release':ref(B/'root-execution-release-v1.json'),
 'root_review':ref(B/'root-decoder-review-v1.json'),'limits':release['limits'],'cpu_seconds_limit':120,
 'gpu_authorized':False,'tensor_payload_access_authorized':True,'whole_container_decode_authorized':True,
 'extra_simulator_steps':0,'automatic_retry_authorized':False,'registered_at':now}
 state.update(current_cpu_task=task,updated_at=now,next_action='Execute one frozen CPU decode of34 containers from both accepted first-active N30 decisions; review content lineage and actual8step feedback, then choose supported next research action. No retry or newGPU release.')
 state['study']['status']='N30_FIRST_ACTIVE_LINEAGE_CPU_DIAGNOSIS_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,goal_achieved=False,target_achieved=False,target_met=False,updated_at=now)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical
 temp=W/'research-state.yaml.n30-lineage-decode-tmp'
 with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(temp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N30 finite lineage CPU diagnostic released\n\nRoot reviewed frozen32KB reader and six source identities; authorized exactly one CPU subprocess,34 whole containers/24273690bytes,2first-active decisions atstep8,120CPU/wall seconds,16GiB AS,2threads. Includes co-resident serialization bytes but analysis is limited to identity/content lineage and already executed8step feedback. No model/scorer/RBF/native replay, API, GPU, new simulator action or protected access. No original archive provenance or total causal influence inferred from content matches. Per-container progress and completed-episode partial only; preparation report finer-granularity wording corrected. Budget and goal unchanged, targetNOT_MET. Release {B/'root-execution-release-v1.json'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(B/'root-execution-registration-v1.json',{'at':now,'task':task,'budget_changed':False,'goal_active':True})
print(json.dumps({'review':ref(B/'root-decoder-review-v1.json'),'release':ref(B/'root-execution-release-v1.json'),'status':state['study']['status']}))

