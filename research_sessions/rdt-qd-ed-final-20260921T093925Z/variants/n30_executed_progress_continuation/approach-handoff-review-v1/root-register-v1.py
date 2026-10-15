"""Close accepted finite CPU diagnosis and register next metadata outer-loop."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,sys,yaml
C=Path(__file__).resolve().parent;P=C.parent;B=P/'lineage-diagnostic-v1/decode-v1';W=P.parents[1]/'study_worktree'
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
spec=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
review=json.loads((B/'root-terminal-review-v1.json').read_text());assert review['decision']=='ACCEPT_BOUNDED_DESCRIPTIVE_DIAGNOSTIC'
now=datetime.datetime.now(datetime.timezone.utc).isoformat();run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['active_iteration'] is None and state['active_controller'] is None and state['current_owned_workers']==[]
 assert state['current_cpu_task']['phase']=='N30_FIRST_ACTIVE_LINEAGE_CPU_DECODE'
 assert state['resource_isolation']['status']=='ACTIVE' and state['resource_isolation']['validation_status']=='PASS'
 budget=copy.deepcopy(state['budget']);lexical=state['worktree']
 snap=C/'registration-before-v1';snap.mkdir(exist_ok=False)
 for name,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(name+'.json'),obj)
 previous=copy.deepcopy(state['current_cpu_task']);previous.update(status='COMPLETE_ACCEPTED_DESCRIPTIVE',closed_at=now,review=ref(B/'root-terminal-review-v1.json'),cpu_seconds=review['cpu_seconds'],result=review['result'],tensor_allowance_exhausted=True,gpu_authorized=False)
 state.setdefault('closed_cpu_tasks',{})['N30_FIRST_ACTIVE_LINEAGE_CPU_DECODE']=previous
 task={'status':'DISPATCHED','phase':'N30_APPROACH_HANDOFF_METADATA_REVIEW','node_id':'14.1','agent':'/root/n22_cpu_executor',
 'scope':ref(C/'root-scope-v1.md'),'previous_diagnostic_review':ref(B/'root-terminal-review-v1.json'),
 'source_base':'6292fc8cffad2eec0f789e023d835ad3c1df146a','cpu_seconds_limit':300,'threads':2,'gpu_authorized':False,'tensor_payload_access_authorized':False,'video_image_decode_authorized':False,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Review first realized EDS-to-nonEDS handoff in BOTH accepted N30 episodes using metadata/static source only, with bounded next-evidence proposal if needed; do not infer Stage error or deploy forced retention from early lineage loss. Continue original activeGoal.',updated_at=now)
 state['study']['status']='N30_APPROACH_HANDOFF_OUTER_REVIEW_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 node=a.node(tree,'14.1');node['post_rejection_lineage_review']=ref(B/'root-terminal-review-v1.json')
 assert state['budget']==budget and state['worktree']==lexical
 tmp=W/'research-state.yaml.n30-handoff-tmp'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N30 lineage result accepted; approach/handoff review dispatched\n\nExactly34containers24273690bytes decodedonce, CPU2.359426458s, outerwall2.455994852s, CUDAfalse; two denied foreign dependency probes retained (guard_clean=false), no successful guardedaccess or retry. Task0 directwarmparents1,1,then0;task1all0. Both final winners uniquely content-supported nonwarm; current8step actual approach89.527/92.151mm tofixedstep8snapshot. No originalarchiveoccurrence/totalcausalclaim or grasp/success inference. These2of18insertions do not support forced retention as nextalgorithm. Root independently reconciled hashes34records/20rounds/16feedbackrows and process exit, without a secondtensor decode.\n\nRoot correction: the frozen reader DID checkpoint every parentround/feedbackstep; earlierrootreviewmistakenly described an in-progress version. Addendum {B/'root-decoder-review-addendum-v1.json'} corrects this; source/release unchanged. Root metadatareviewv1 failed on obsoletefield loads; v2 uses actual load_invocations/decode_succeeded, oldfailure retained, no payload reread.\n\nNext bounded metadata/static review targets firstrealizedEDS-to-nonEDS handoff in bothacceptedN30episodes; missingEDSmetric is not Stage-error proof. No payload/image/video/GPUpermission yet. Caps578/100, privatebudget and protectedsets unchanged; targetNOT_MET. Acceptedreview {B/'root-terminal-review-v1.json'}. Scope {C/'root-scope-v1.md'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(C/'root-registration-v1.json',{'at':now,'closed_cpu_task':previous,'task':task,'budget_changed':False,'goal_active':True})
print(json.dumps(task))

