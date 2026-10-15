"""Root state registration for accepted Phase A and decoder preparation only."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
B=Path(__file__).resolve().parent;D=B.parent;W=D.parent.parents[1]/'study_worktree';run='rdt-qd-ed-final-20260921T093925Z'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
review=json.loads((D/'root-inventory-review-v1.json').read_text());assert review['decision']=='ACCEPT_METADATA_INVENTORY'
now=datetime.datetime.now(datetime.timezone.utc).isoformat();session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['active_iteration'] is None and state['current_cpu_task']['phase']=='N30_LINEAGE_METADATA_INVENTORY'
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 before=B/'registration-before-v1';before.mkdir(exist_ok=False)
 for name,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(before/(name+'.json'),obj)
 previous=copy.deepcopy(state['current_cpu_task']);previous.update(status='COMPLETE_METADATA_ONLY',closed_at=now,review=ref(D/'root-inventory-review-v1.json'))
 state.setdefault('closed_cpu_tasks',{})['N30_LINEAGE_METADATA_INVENTORY']=previous
 task={'status':'DISPATCHED','phase':'N30_LINEAGE_DECODER_PREPARATION','node_id':'14.1','agent':'/root/n22_cpu_executor',
 'scope':ref(B/'root-decoder-preparation-scope-v1.md'),'inventory_review':ref(D/'root-inventory-review-v1.json'),
 'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','cpu_seconds_limit':300,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':False,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Prepare/freeze the bounded34-container CPU lineage reader; root review then separate one-shot decode release. No newGPU candidate until interpreted evidence. Continue active Goal.',updated_at=now)
 state['study']['status']='N30_POST_REJECTION_LINEAGE_DECODER_PREPARATION_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lexical
 tmp=W/'research-state.yaml.n30-lineage-prepare-tmp'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N30 first-active inventory accepted; decoder preparation\n\nRoot independently verified28deliveryrefs, accepted source/plan/receipt identities, both full-metric earliest-active rules and exact34-container index selection/stat. Both task0/1 targetstep8; proposed24273690bytes. Root tensorreads0, CPU{review['root_cpu_seconds']:.6f}s. Original worker numerical audit remains inherited; absence of direct ancestry cannot exclude QD/ED population coupling. PhaseA closed; CPUreader preparation dispatched to existingexecutor, no payload/GPU/API/simulator permission. Caps/buckets/protected phases unchanged; goalNOT_MET. Review {D/'root-inventory-review-v1.json'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(B/'root-preparation-registration-v1.json',{'at':now,'previous_task':previous,'task':task,'budget_changed':False,'goal_active':True})
print(json.dumps(task))

