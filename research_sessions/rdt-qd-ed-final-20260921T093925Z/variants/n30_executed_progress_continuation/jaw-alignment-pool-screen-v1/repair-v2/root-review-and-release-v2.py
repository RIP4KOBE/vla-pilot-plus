"""ROOT static review and one manual CPU recovery; no native payload reads."""
from pathlib import Path
import ast,copy,datetime,hashlib,importlib.util,json,os,sys,time,yaml
V=Path(__file__).resolve().parent;Q=V.parent;P=Q.parent;W=P.parents[1]/'study_worktree'
start=time.process_time()
def raw(p):
 p=Path(p);assert p.suffix not in {'.pt','.mp4','.png','.jpg'},str(p)
 return p.read_bytes()
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(raw(p)).hexdigest(),'bytes':len(raw(p))}
def check(x):
 b=raw(x['path']);assert hashlib.sha256(b).hexdigest()==x['sha256'],x['path']
 if 'bytes' in x:assert len(b)==x['bytes'],x['path']
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
delivery=V/'delivery-manifest-v2.json'
assert ref(delivery)['sha256']=='e19292dbaaf3ff479256c087326b243eacf2fd8432d73b20e22d1c102777880d'
items=json.loads(raw(delivery))['files']
for x in items:check(x)
m=json.loads(raw(V/'calculation-source-manifest-v2.json'))
for k in ['reader','input_manifest','measurement_declaration','successful_archive_lineage_reader','old_reader','old_failure_resource','old_external_receipt','repair_scope']:check(m[k])
for x in m['static_source_files']:check(x)
assert m['reader']['sha256']=='e7036561b172bc8fdc359b24fb9a5329c9d69ab9c5186a67e517b7cb9a69a8b8'
old=ast.parse(raw(m['old_reader']['path']));new=ast.parse(raw(m['reader']['path']))
def fun(t,n):return next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name==n)
assert ast.dump(fun(old,'geometry'))==ast.dump(fun(new,'geometry'))
calls=[x for x in ast.walk(fun(new,'main')) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='analyze']
assert len(calls)==1 and len(calls[0].args)==3
assert not any((V/n).exists() for n in ['invocation-v1.json','resource-v1.json','result-v1.json','root-manual-execution-release-v2.json'])
assert not (Path('/proc')/'3922644').exists()
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
review={'decision':'ACCEPT_STATIC_BINDING_REPAIR_RELEASE_ONE_MANUAL_CPU_INVOCATION','at':now,'delivery':ref(delivery),'source_manifest':ref(V/'calculation-source-manifest-v2.json'),'reader':m['reader'],'declaration':m['measurement_declaration'],'verified_delivery_refs':len(items),'geometry_ast_unchanged':True,'prior_argument_static_verified':True,'independent_source_checks':['actual Q0 archive_global_best population, sorted occupied cells, N<=16; no N5 terminal assumptions','canonical_initial/initial_population iter-1 and canonical_offspring/rollout iter0..9; native samples, canonical fingerprints, score scope/order/quality bound','all equal native-content occurrences must agree in projection/quality/cost/origin; otherwise Unknown, no favorable choice','target from N30 recognized current context and bound target/tracker; no N5 fields','controller.ee_pos projection and observed grip_site differ in source; no equality assertion or physical-execution claim','frozen geometry/minima/rank semantics retained; unknown rows withhold full-pool ranks'],'old_failure':ref(Q/'root-terminal-review-v1.json'),'cumulative_failed_plus_recovery_caps':{'cpu_seconds':120,'wall_seconds':180,'encoded_bytes':67108864,'zip_or_storage_bytes':134217728},'recovery_limits':{'cpu_seconds':118,'wall_seconds':178,'threads':2,'affinity':[0,1],'containers':4,'encoded_bytes':24183110},'root_native_reads_or_scientific_numeric_replays':0,'root_review_cpu_seconds':time.process_time()-start,'goal_achieved':False}
put(V/'root-static-review-v2.json',review)
release=json.loads(raw(V/'root-release-template.disabled.v2.json'))
release.update(executable=True,acknowledge_v1_two_containers_already_decoded=True,root_signature_or_review=ref(V/'root-static-review-v2.json'),released_at=now,automatic_retry_authorized=False)
assert release['reader']==m['reader'] and release['input_manifest']==m['input_manifest']
check(release['source_manifest'])
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 assert state['current_cpu_task']['phase']=='N30_FIXED_HANDOFF_JAW_POOL_BINDING_REPAIR_V2'
 assert state['current_owned_workers']==[] and state['active_controller'] is None and state['active_plan'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=V/'registration-before-execution-v2';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 prep=copy.deepcopy(state['current_cpu_task']);prep.update(status='STATIC_REPAIR_REVIEWED',closed_at=now,review=ref(V/'root-static-review-v2.json'))
 state.setdefault('closed_cpu_tasks',{})[prep['phase']]=prep
 put(V/'root-manual-execution-release-v2.json',release)
 task={'status':'DISPATCHED_MANUAL_RECOVERY','phase':'N30_FIXED_HANDOFF_JAW_POOL_SCREEN_RECOVERY_V2','node_id':'14.1','agent':'/root/n22_cpu_executor','scope':ref(Q/'root-repair-scope-v2.md'),'release':ref(V/'root-manual-execution-release-v2.json'),'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','cpu_seconds_limit':118,'wall_seconds_limit':178,'threads':2,'gpu_authorized':False,'native_payload_reads_authorized':'exact four listed containers; one per file, manual second read of task0 acknowledged','automatic_retry_authorized':False,'tasks':[0,1],'decision_id':'e0:d3:s16','registered_at':now}
 state.update(current_cpu_task=task,next_action='Execute the repaired fixed final-archive pool screen once under the exact release, then independently review all rows and use the evidence for one next mechanism decision; no GPU or protected-phase access.',updated_at=now)
 state['study']['status']='N30_CANDIDATE_POOL_CPU_RECOVERY_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU_MANUAL_RECOVERY',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 node=a.node(tree,'14.1')
 node['previous_cpu_task_before_pool_recovery']=copy.deepcopy(node.get('cpu_task'))
 node['cpu_task']=task
 node['post_rejection_pool_static_review']=ref(V/'root-static-review-v2.json')
 node['insight']='N30 GPU cohort CLOSED valid futility: C0/Q0/N30 each0/2, tasks2/3 unrun Unknown, max2/4 below frozen3/4. Eighteen continuation insertions active but no task gain; two earlier engineering-invalid charges retained. Closed lineage/handoff/visual/calibrated geometry diagnoses establish selected-prefix behavior only, not grasp causality. Fixed decision16 archive-pool CPU screen now manually repaired after unentered missing-argument and incorrect N5 population assumptions; no result yet.'
 parent=a.node(tree,'14');parent['status']='done';parent['insight']='One progress-conditioned Q0 continuation proposal (N30) failed its frozen Dev screen; general continuity benefit remains unestablished. No validation/formal promotion; post-rejection diagnostics guide a new mechanism.'
 a.node(tree,tree['root_id'])['insight']='Goal NOT_MET. N29 C0/Q0/N28/N29 all0/6; N30 C0/Q0/N30 all0/2 and rejected by its own3/4 first-four gate. N30 inserts competing tails but task benefit unestablished. Accepted handoff observations: task0 guided closing prefix already withdraws before guidance-off; task1 guided approach stays open, later off-guidance closes. Fixed current hand-frame point geometry is a proxy, not object capture. One repaired CPU screen compares all final archive elites at the same two decision16 pools; no new GPU candidate released. Budget403/578 dispatches and53.80872756284531/100 GPUh; week expansion pending, validation/formal protected.'
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-pool-release-v2'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Root-reviewed archive binding repair released once\n\nStatic source and {len(items)} delivery references verified. Same geometry AST; no N5/terminal-population assumption. Exactly four previously declared containers, old task0 two reads acknowledged, recovery118CPU/178wall, combined bytes36274537. Original failure and denied probes preserved. No root numeric replay or new GPU charge. Tree summaries refreshed to closed N30 0/2 futility and current diagnostic phase; historical results unchanged. Goal NOT_MET.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(V/'root-execution-registration-v2.json',{'closed_preparation':prep,'task':task,'budget_changed':False})
print(json.dumps({'release':ref(V/'root-manual-execution-release-v2.json'),'review':ref(V/'root-static-review-v2.json'),'task':task['phase']}))

