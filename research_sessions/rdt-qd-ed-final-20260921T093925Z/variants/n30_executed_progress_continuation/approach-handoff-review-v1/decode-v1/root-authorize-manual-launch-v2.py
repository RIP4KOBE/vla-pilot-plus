"""Authorize one explicit launcher repair after verified pre-invocation CPU-limit failure."""
from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,resource,sys,yaml
H=Path(__file__).resolve().parent;P=H.parent.parent;W=P.parents[1]/'study_worktree'
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def put(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2);f.write('\n')
ext=json.loads((H/'external-execution-v1.json').read_text());log=(H/'execution-v1.log').read_text()
assert ext['exit_code']==1 and ext['process_reaped'] and ext['timeout_process_identity']['pid']==3856346
assert not Path('/proc/3856346').exists()
assert 'line 7' in log and 'resource.setrlimit(resource.RLIMIT_CPU,(120,120))' in log and 'not allowed to raise maximum limit' in log
assert ref(H/'decode_cpu_v1.py')['sha256']=='4f11e72f7e15c81c5fe5094499e74ebbfed5113e05e467e2adae33f108497ed0'
assert ref(H/'root-execution-release-v1.json')['sha256']=='244827f622422add4b043f777490fa91e890d11cc10cc668166631171994773a'
names=['invocation-v1.json','progress-v1.jsonl','partial-v1.json','result-v1.json','resource-v1.json','summary-v1.md']
assert not any((H/n).exists() for n in names)
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
authorization={'schema':'n30-handoff-manual-launch-recovery-v2','authorized':True,'created_at':now,'manual_launch_ordinal':2,'maximum_additional_launches':1,'previous_failure':ref(H/'external-execution-v1.json'),'previous_traceback':ref(H/'execution-v1.log'),'root_observations':{'failed_pid_absent':True,'reader_output_names_absent':names,'fresh_parent_rlimit_cpu':list(resource.getrlimit(resource.RLIMIT_CPU))},'reader':ref(H/'decode_cpu_v1.py'),'scientific_release_unchanged':ref(H/'root-execution-release-v1.json'),'command_argv_unchanged':json.loads((H/'command.disabled.v1.json').read_text())['argv'],'stdout_stderr_path':str(H/'execution-v2.log'),'external_receipt_path':str(H/'external-execution-v2.json'),'repair':'Launch from fresh parent with inherited CPU hard limit infinity or at least120; do not set administrative30CPU hard limit before forking reader. Frozen reader sets120/120; frozen outer timeout enforces120wall. Measure parent administrative CPU separately, at most30 seconds.','single_payload_decode_allowance_unchanged':{'containers':68,'bytes':24429984,'reads_per_file':1,'loads_per_file':1},'reason':'Prior invocation died at source line7 before authorize(), torch import, audit hook or payload access. New manual launch repairs only inherited launcher limit. No successful scientific data execution is repeated.','preserve_previous_logs_receipt':True,'automatic_retry_authorized':False,'source_data_selection_limits_unchanged':True,'gpu_authorized':False,'extra_simulator_steps':0,'post_run':'Report actual external wall and child/parentCPU, output/guard resources; independent root acceptance still required.'}
put(H/'root-manual-launch-authorization-v2.json',authorization)
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator'
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 assert state['current_cpu_task']['phase']=='N30_FIRST_HANDOFF_CPU_DECODE' and state['current_owned_workers']==[] and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=H/'manual-recovery-before-v2';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 old=copy.deepcopy(state['current_cpu_task']);old.update(status='STARTUP_ERROR_PRE_INVOCATION',closed_at=now,external_receipt=ref(H/'external-execution-v1.json'),traceback=ref(H/'execution-v1.log'),payload_reads=0,child_cpu_seconds=ext['child_cpu_seconds_including_wrapper'],wall_seconds=ext['external_wall_seconds_including_process_start_exit'])
 state.setdefault('closed_cpu_tasks',{})['N30_FIRST_HANDOFF_CPU_DECODE_LAUNCH1']=old
 task=copy.deepcopy(state['current_cpu_task']);task.update(status='DISPATCHED',phase='N30_FIRST_HANDOFF_CPU_MANUAL_STARTUP_RECOVERY',manual_launch_ordinal=2,manual_authorization=ref(H/'root-manual-launch-authorization-v2.json'),registered_at=now)
 state.update(current_cpu_task=task,next_action='One explicitly reviewed launcher recovery with unchanged frozen reader/data/120CPU+wall limits after zero-payload inherited30CPU startup failure. No automatic retries; preserve failure and continue original Goal.',updated_at=now)
 state['study']['status']='N30_HANDOFF_CPU_STARTUP_RECOVERY_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n30-handoff-manual-v2'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — Pre-invocation launcher failure retained; one explicit startup recovery\n\nLaunch1 inherited30CPU hard limit from an administrative wrapper, failed at reader line7 setting120/120. Exit1, childCPU{ext['child_cpu_seconds_including_wrapper']}s, externalwall{ext['external_wall_seconds_including_process_start_exit']}s; timeoutPID3856346 independently absent. No invocation/Torch/payload or scientific result. Root authorizes one manual launch2 with unchanged4f11e72f reader and original244827f release, fresh parent CPU hardlimit>=120; new log/receipt v2 preserve v1. Total authorized data remains68 containers each one read/load, no automatic retry, no GPU/episode budget charge or reserve change. Original Goal NOT_MET. Authorization {H/'root-manual-launch-authorization-v2.json'}.\n"
 for p in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with p.open('a') as f:f.write(note)
 r.durable_json(H/'root-manual-recovery-registration-v2.json',{'previous':old,'task':task,'budget_changed':False})
print(json.dumps(ref(H/'root-manual-launch-authorization-v2.json')))
