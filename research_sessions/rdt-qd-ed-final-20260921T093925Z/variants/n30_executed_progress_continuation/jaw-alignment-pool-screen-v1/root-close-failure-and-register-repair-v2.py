"""Close a failed CPU diagnostic without replaying payloads or metrics."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
Q=Path(__file__).resolve().parent;P=Q.parent;W=P.parents[1]/'study_worktree'
started=time.process_time()
def raw(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'},str(p)
 return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(raw(p)).hexdigest()}
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
manifest=Q/'delivery-manifest-v1.json'
assert ref(manifest)['sha256']=='7bbb420f11f2f737957c37f51f7a07b158f0db30cd7bd64c51afaa6fc0ad6551'
items=json.loads(raw(manifest))['files']
for item in items:
 b=raw(item['path']);assert hashlib.sha256(b).hexdigest()==item['sha256'] and len(b)==item['bytes'],item['path']
res=json.loads(raw(Q/'resource-v1.json'));ext=json.loads(raw(Q/'external-execution-v1.json'));cl=json.loads(raw(Q/'closure-v1.json'))
assert res['complete'] is False and res['completed_episodes']==0 and res['error']['type']=='TypeError'
assert res['pid']==ext['child_pid']==3922644 and ext['exit_code']==1 and ext['wait_reaped'] and not (Path('/proc')/str(res['pid'])).exists()
reads=[x for x in res['reads'] if x['kind']=='payload']
assert len(reads)==2 and sum(x['bytes'] for x in reads)==12091427 and all(x['load_invocations']==1 and x['decode_succeeded'] for x in reads)
assert len(res['denied_probes'])==6 and not res['guard_clean'] and not res['cuda_initialized']
assert not (Q/'result-v1.json').exists() and not (Q/'partial-v1.json').exists()
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review={'decision':'CLOSE_INCOMPLETE_ENGINEERING_ERROR_NO_NUMERICAL_FINDING','at':now,'delivery_manifest':ref(manifest),'verified_output_refs':len(items),'process_exited':True,'child_cpu_seconds':ext['child_cpu_seconds'],'external_wall_seconds':ext['wall_seconds'],'payload_containers_read':2,'encoded_bytes_read':12091427,'completed_episodes':0,'guard_clean':False,'denied_probes_count':6,'cuda_initialized':False,'no_driver_probe_claim':False,'reported_failure':res['error'],'root_static_additional_failure':'Reader incorrectly assumes N5 terminal population/grasp selector and iter9 scoring. N30 uses Q0 archive_global_best; final population is sorted archive elites across canonical batches. No numerical function entered, so no numerical conclusions from this pass.','source_refs':[ref(W/'core/rdt_policy_steer.py'),ref(W/'core/qd_ed.py')],'source_lines':['rdt_policy_steer.py:7154 elite_tensors -> select_global_best, terminal population guarded by terminal_mode','qd_ed.py:810 elite_tensors uses sorted occupied cells; entry snapshot retains fingerprint/source_iter/insert_sequence'],'numerical_findings':'Unknown','goal_achieved':False,'root_payload_or_scientific_measurements':0,'repair_scope':ref(Q/'root-repair-scope-v2.md'),'root_review_cpu_seconds':time.process_time()-started}
put(Q/'root-terminal-review-v1.json',review)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 assert state['current_cpu_task']['phase']=='N30_FIXED_HANDOFF_JAW_ALIGNMENT_POOL_SCREEN'
 assert state['current_owned_workers']==[] and state['active_controller'] is None and state['active_plan'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=Q/'registration-before-repair-v2';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 old=copy.deepcopy(state['current_cpu_task']);old.update(status='INCOMPLETE_ENGINEERING_ERROR',closed_at=now,review=ref(Q/'root-terminal-review-v1.json'),calculation_allowance_closed=True,cpu_seconds=ext['child_cpu_seconds'],wall_seconds=ext['wall_seconds'],native_reads=reads)
 state.setdefault('closed_cpu_tasks',{})[old['phase']]=old
 task={'status':'DISPATCHED_STATIC_REPAIR_ONLY','phase':'N30_FIXED_HANDOFF_JAW_POOL_BINDING_REPAIR_V2','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(Q/'root-repair-scope-v2.md'),'preceding_review':ref(Q/'root-terminal-review-v1.json'),'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','gpu_authorized':False,'native_payload_reads_authorized':False,'numerical_calculation_authorized':False,'automatic_retry_authorized':False,'tasks':[0,1],'decision_id':'e0:d3:s16','registered_at':now}
 state.update(current_cpu_task=task,next_action='Repair diagnostic function call and archive/canonical provenance mapping statically; ROOT review binding before one bounded manual recovery. Preserve all failed-run evidence. No GPU or native reads during preparation.',updated_at=now)
 state['study']['status']='N30_CANDIDATE_POOL_BINDING_REPAIR_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU_STATIC_REPAIR',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 a.node(tree,'14.1')['post_rejection_pool_v1_failure_review']=ref(Q/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-pool-repair-v2'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Candidate pool reader failed; static binding repair\n\nMissing prior argument stopped before any numerical analysis; task0 two containers/12091427 bytes each read once, task1 untouched. Child CPU {ext['child_cpu_seconds']}s, wall {ext['wall_seconds']}s; six denied import probes retained, CUDA uninitialized, no clean-guard/no-driver-probe claim. ROOT verified all {len(items)} manifest entries and process exit. Additional static error: final population is Q0-derived cross-round archive elites, not N5 terminal iter9 candidates. Original 16-row wording is corrected prospectively to all actually occupied final archive rows, N<=16; no outcome-dependent sampling or formula changes. Static preparation only until root binding review. Goal NOT_MET; budgets, protected phases and GPU authorization unchanged.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(Q/'root-repair-registration-v2.json',{'closed_task':old,'task':task,'budget_changed':False})
print(json.dumps({'review':ref(Q/'root-terminal-review-v1.json'),'verified_refs':len(items),'task':task['phase']}))

