"""Review frozen reader statically and register one bounded CPU diagnosis."""
from pathlib import Path
import ast,copy,datetime,hashlib,importlib.util,json,os,subprocess,sys,time,yaml
H=Path(__file__).resolve().parent;C=H.parent;P=C.parent;W=P.parents[1]/'study_worktree';t=time.process_time()
def ref(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'}
 return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def check(q):
 got=ref(q['path']);assert got['sha256']==q['sha256'],q['path']
 if 'bytes' in q:assert Path(q['path']).stat().st_size==q['bytes'],q['path']
def put(p,obj):
 with Path(p).open('x') as f:json.dump(obj,f,indent=2);f.write('\n')
assert ref(H/'delivery-manifest-v1.json')['sha256']=='a19d1b64a584f8e2753fa2ff867cf0a02970bc5c1c14acdd4b55d8909b079022'
delivery=json.loads((H/'delivery-manifest-v1.json').read_text());assert delivery['frozen'] and not delivery['executed']
for q in delivery['files']:check(q)
manifest=json.loads((H/'decoder-source-manifest-v1.json').read_text())
for key in ['reader','input_bindings','protocol','phase_c_review','preparation_scope','reused_reader']:check(manifest[key])
for q in manifest['scientific_source_files']:check(q)
assert ref(H/'decode_cpu_v1.py')['sha256']=='4f11e72f7e15c81c5fe5094499e74ebbfed5113e05e467e2adae33f108497ed0'
source=(H/'decode_cpu_v1.py').read_text();parsed=ast.parse(source);compile(parsed,str(H/'decode_cpu_v1.py'),'exec')
command=json.loads((H/'command.disabled.v1.json').read_text());assert not command['executable'] and command['one_attempt_only']
for n in command['expected_output_names']:assert not (H/n).exists(),n
assert not (H/'summary-v1.md').exists() and not (H/'execution-v1.log').exists()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==manifest['source_commit']=='6292fc8cffad2eec0f789e023d835ad3c1df146a'
resource=json.loads((H/'preparation-resource-v1.json').read_text())
assert resource['preparation_reader_runs']==resource['payload_opens']==resource['payload_hash_measurements']==resource['payload_decodes']==resource['torch_numpy_production_imports']==resource['scientific_tests']==0
review={'decision':'ACCEPT_FROZEN_READER_FOR_ONE_BOUNDED_CPU_RUN','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'delivery':ref(H/'delivery-manifest-v1.json'),'reader':manifest['reader'],'source_manifest':ref(H/'decoder-source-manifest-v1.json'),'verified_delivery_refs':len(delivery['files']),'verified_scientific_sources':len(manifest['scientific_source_files']),'static_syntax':'AST parse+compile without execution','root_checks':['exact2 accepted cells and first step16->24 decisions','68 fixed whole containers one read/hash+CPU weights_only load each','provider fields digest-only, context/selected fields narrowed, excluded candidates/scores/reward not analyzed','recorded decode/commit/actual command byte equality and exact outcome/return identity','strict scalar Boolean boundary','history committed/ack not mistaken for actual execution','fixed target snapshot, old-reference and Unknown semantics','partial checkpoint per actual step and decision','no automatic retries or production/model/scorer/simulator imports','CUDA hidden; no zero-driver-probe claim; denied dependency probes retained','limits120CPU/120externalwall,16GiBAS,64MiBZIP+storage,2threads affinity0,1'],'known_limits':['Static acceptance is not runtime success or scientific causal evidence.','Whole-container decode includes excluded co-resident payloads; only whitelist is analyzed/exported.','Grasp, semantic target correctness and original Stage-query disable cause remain unavailable in this route.'],'lookup_note':'Root first tried nonexisting preparation-delivery-v1.json, then used actual delivery-manifest-v1.json; no payload access or execution.','payload_reads_hashes_decodes':0,'review_cpu_seconds':time.process_time()-t,'goal_achieved':False}
put(H/'root-decoder-review-v1.json',review)
release=copy.deepcopy(command['root_release_fields_disabled_example'])
release.update(executable=True,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),root_review=ref(H/'root-decoder-review-v1.json'),whole_container_decode_authorized=True,analysis_export_scope='Exact disabled proposal whitelist; no candidate/scoring/reward/provider-body/privileged-state analysis',automatic_retry_authorized=False,extra_simulator_steps=0,gpu_authorized=False)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task']['phase']=='N30_HANDOFF_DECODER_PREPARATION'
 assert state['active_controller'] is None and state['current_owned_workers']==[] and state['active_iteration'] is None
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 snap=H/'release-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 put(H/'root-execution-release-v1.json',release)
 prev=copy.deepcopy(state['current_cpu_task']);prev.update(status='COMPLETE_PREPARATION_ONLY',closed_at=now,review=ref(H/'root-decoder-review-v1.json'),payload_reads=0)
 state.setdefault('closed_cpu_tasks',{})[prev['phase']]=prev
 task={'status':'DISPATCHED','phase':'N30_FIRST_HANDOFF_CPU_DECODE','node_id':'14.1','agent':'/root/n22_cpu_executor','source_base':manifest['source_commit'],'reader':manifest['reader'],'release':ref(H/'root-execution-release-v1.json'),'root_review':ref(H/'root-decoder-review-v1.json'),'limits':release['limits'],'cpu_seconds_limit':120,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':True,'whole_container_decode_authorized':True,'video_image_decode_authorized':False,'automatic_retry_authorized':False,'extra_simulator_steps':0,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Run exactly one bounded N30 first-handoff CPU diagnosis on fixed existing68containers; then independent root result review before another hypothesis. No GPU or automatic retry. Continue original active Goal.',updated_at=now)
 state['study']['status']='N30_FIRST_HANDOFF_CPU_DIAGNOSTIC_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical
 tmp=W/'research-state.yaml.n30-handoff-release-tmp'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N30 handoff reader reviewed and one CPU diagnosis released\n\nFrozen reader4f11e72f7e15c81c5fe5094499e74ebbfed5113e05e467e2adae33f108497ed0 independently reviewed. Exactly68 whole containers24429984bytes,4 contexts/32 actualsteps16..31, one read/load each,120CPU/120externalwall,2threads affinity0,1,16GiBAS/64MiBZIP+storage. Candidate/scoring/provider-body co-resident values may deserialize but remain outside analysis/export. No runtime success yet, no GPU, no simulator branches/retry. Prior static filename errors retained. Budget/caps/reserves unchanged; original Goal NOT_MET. Review {H/'root-decoder-review-v1.json'}, release {H/'root-execution-release-v1.json'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(H/'root-release-registration-v1.json',{'at':now,'task':task,'previous_task':prev,'budget_changed':False})
print(json.dumps({'review':ref(H/'root-decoder-review-v1.json'),'release':ref(H/'root-execution-release-v1.json'),'phase':task['phase']}))
