from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,subprocess,sys,yaml
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';I=P/'implementation'
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
D=json.loads((P/'delivery-manifest-phase-a-v1.json').read_text());S=json.loads((P/'source-manifest-phase-a-v1.json').read_text())
for x in D['files']+S['files']:
 assert ref(x['path'])=={k:x[k] for k in ('path','sha256','bytes')},x['path']
for x in S['files']:
 b=subprocess.check_output(['git','show',S['commit']+':'+x['relative_path']],cwd=I);assert hashlib.sha256(b).hexdigest()==x['sha256']
assert subprocess.check_output(['git','status','--porcelain'],cwd=I)==b''
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=I).decode().strip()==S['commit']
assert subprocess.check_output(['git','rev-parse','HEAD^'],cwd=I).decode().strip()==S['base_commit']
receipts=[]
for n in (1,2):
 e=json.loads((P/f'cpu-run{n}-external.json').read_text());z=json.loads((P/f'cpu-run{n}-resource.json').read_text());assert not Path('/proc/'+str(e['pid'])).exists();assert e['reaped'] and not e['timeout'];assert z['affinity']==[0,1] and z['threads']==2 and z['cuda_initialized'] is False
 if n==2:assert e['exit_code']==z['exit_code']==0 and z['guard_clean'] and not z['denied']
 receipts.append({'external':ref(P/f'cpu-run{n}-external.json'),'resource':ref(P/f'cpu-run{n}-resource.json'),'exit_code':e['exit_code'],'pid_absent':True,'guard_clean':z['guard_clean']})
review={'schema':'n31-root-phase-a-review-v1','reviewed_at':now,'decision':'ACCEPT_PURE_HELPER_AND_STATIC_CONTRACT_ADVANCE_CPU_INTEGRATION','commit':S['commit'],'base':S['base_commit'],'verified_file_entries':22,'source_clean':True,'source_reviewed':['core/qd_capture_dwell_proposal.py','tests/test_qd_capture_dwell_proposal.py','docs/experiments/n31_capture_dwell_phase_a.md'],'delivery':ref(P/'delivery-manifest-phase-a-v1.json'),'report':ref(P/'cpu-phase-a-report-v1.md'),'receipts':receipts,'distinct_synthetic_cases':37,'final_guard_clean':True,'run1_guard_failure_preserved':True,'root_reran_tests':False,'implementation_benefit_unknown':True,'limitations':['Pure tests do not exercise production policy integration.','Literal inclusive binary64 prism is frozen; not a physical grasp predicate.','Zero subsequent pose increments only approximate dwell; observed wrist/aperture frozen.','Current rollout scores internally: placement must precede the existing score with no additional call.'],'score':'Unknown','target_achieved':False,'gpu_authorized':False}
assert not (P/'root-phase-a-review-v1.json').exists();r.durable_json(P/'root-phase-a-review-v1.json',review)
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 old=state['current_cpu_task'];assert old['phase']=='N31_CAPTURE_DWELL_CPU_PHASE_A' and old['node_id']=='15.1'
 assert state['current_owned_workers']==[] and state['active_plan'] is None and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=P/'phase-b-registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 task={'status':'DISPATCHED','phase':'N31_CAPTURE_DWELL_CPU_PHASE_B','node_id':'15.1','agent':'/root/n22_cpu_executor','scope':ref(P/'cpu-phase-b-production-integration-v1.md'),'preceding_review':ref(P/'root-phase-a-review-v1.json'),'implementation_worktree':str(I),'branch':'codex/n31-capture-dwell','source_base':S['commit'],'test_cpu_seconds_limit':1200,'test_wall_seconds_limit':1800,'threads':2,'historical_tensor_or_video_reads_authorized':False,'new_exposed_data_measurements_authorized':False,'gpu_authorized':False,'production_hookup_authorized':True,'registered_at':now}
 state.update(current_cpu_task=task,next_action='Integrate frozen N31 capture-dwell opt-in into original Q0 with canonical projection provenance and cached current observation. Validate actual production call chains synthetically on CPU; no GPU release or budget change.',updated_at=now)
 state['active_iteration'].update(status='CPU_PHASE_B',source_base=S['commit'],phase_a_review=task['preceding_review'],execution_authorized=False,validation_authorized=False,formal_authorized=False,target_achieved=False)
 state['study']['status']='N31_CAPTURE_DWELL_CPU_PHASE_B_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 leaf=a.node(tree,'15.1');assert leaf['status']=='running';leaf.update(phase='CPU_PHASE_B',cpu_task=task,code_ref=S['commit'],phase_a_review=task['preceding_review'],gpu_execution_authorized=False,target_achieved=False)
 leaf['result']='Pure helper37 distinct synthetic cases pass with final clean isolation; first pycache guard failure retained. Production integration now authorized on CPU; robot efficacy Unknown.'
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n31-phase-b-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N31 phase A accepted; CPU production integration\n\nRoot independently checked22 file entries, four Git blobs, clean commit {S['commit']}, both test processes absent, and final37-case clean guard receipt. First pycache guard failure retained. Synthetic helper correctness does not establish production or task benefit. Phase B permits exact frozen opt-in integration/cache/current-observation/passive evidence and actual-method synthetic tests, CPU1200s/wall1800s cumulative,2threads. Protocol: {P/'cpu-phase-b-production-integration-v1.md'}. GPU/protected phases closed; budget unchanged; target NOT_MET.\n"
 for path in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with path.open('a') as f:f.write(note)
 r.durable_json(P/'root-cpu-phase-b-registration-v1.json',{'task':task,'budget_changed':False,'previous_task':old})
print(json.dumps({'review':ref(P/'root-phase-a-review-v1.json'),'task':task['phase'],'scope':task['scope']}))
