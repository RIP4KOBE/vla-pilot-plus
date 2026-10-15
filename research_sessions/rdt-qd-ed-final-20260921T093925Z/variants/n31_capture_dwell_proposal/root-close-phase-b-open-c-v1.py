from pathlib import Path
import copy,datetime,hashlib,importlib.util,json,os,subprocess,sys,yaml
P=Path(__file__).resolve().parent;W=P.parents[1]/'study_worktree';I=P/'implementation'
def ref(p):
 p=Path(p);b=p.read_bytes();return {'path':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)}
sys.path[:0]=[str(W),str(W/'scripts')]
from scripts import qd_ed_final_runner as r
sp=importlib.util.spec_from_file_location('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;coord=session/'.coordinator';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
D=json.loads((P/'delivery-manifest-phase-b-v1.json').read_text());S=json.loads((P/'source-manifest-phase-b-v1.json').read_text());L=json.loads((P/'cpu-resource-ledger-phase-b-v1.json').read_text())
entries=D['files']+S['files']+S['final_test_bound_sources']
for x in entries:
 assert ref(x['path'])=={k:x[k] for k in ('path','sha256','bytes')},x['path']
for x in S['files']+S['final_test_bound_sources']:
 b=subprocess.check_output(['git','show',S['commit']+':'+x['relative_path']],cwd=I);assert hashlib.sha256(b).hexdigest()==x['sha256'] and len(b)==x['bytes']
for x in S['files']:
 if x['status']=='M':
  b=subprocess.check_output(['git','show',S['base_commit']+':'+x['relative_path']],cwd=I);assert hashlib.sha256(b).hexdigest()==x['base_sha256'] and len(b)==x['base_bytes']
for path in S['phase_a_files_unchanged']:
 assert subprocess.check_output(['git','show',S['phase_a_commit']+':'+path],cwd=I)==(I/path).read_bytes()
assert subprocess.check_output(['git','status','--porcelain'],cwd=I)==b''
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=I).decode().strip()==S['commit']
assert subprocess.run(['git','apply','--reverse','--check',str(P/'phase-b-source.diff')],cwd=I,capture_output=True).returncode==0
bound=json.loads((P/'cpu-phase-b-run6-source.json').read_text())
for path,sha in bound['sources'].items():assert ref(I/path)['sha256']==sha
receipts=[];cpu=wall=0
for n in range(1,7):
 e=json.loads((P/f'cpu-phase-b-run{n}-external.json').read_text());z=json.loads((P/f'cpu-phase-b-run{n}-resource.json').read_text())
 assert not Path('/proc/'+str(e['pid'])).exists() and e['reaped']
 assert z['affinity']==[0,1] and z['threads']==2 and z['cuda_initialized'] is False and z['guard_clean'] and not z['denied']
 assert e['exit_code']==z['exit_code']
 if n>=4:assert ref(P/f'cpu-phase-b-run{n}-source.json')['sha256']==e['source_binding_sha256']
 if n==6:assert e['exit_code']==0
 cpu+=e['child_cpu_seconds'];wall+=e['wall_seconds']
 receipts.append({'external':ref(P/f'cpu-phase-b-run{n}-external.json'),'resource':ref(P/f'cpu-phase-b-run{n}-resource.json'),'exit_code':e['exit_code'],'pid_absent':True,'guard_clean':True})
assert abs(cpu-L['aggregate_test_cpu_seconds'])<1e-8 and abs(wall-L['aggregate_test_wall_seconds'])<1e-8
assert cpu<1200 and wall<1800 and len(set(L['final_nodeids']))==37
review={'schema':'n31-root-phase-b-review-v1','reviewed_at':now,'decision':'ACCEPT_PRODUCTION_INTEGRATION_ADVANCE_CPU_NATIVE_RUNTIME','commit':S['commit'],'base':S['base_commit'],'phase_a_commit':S['phase_a_commit'],'verified_file_entries':len(entries),'git_source_entries_verified':25,'modified_base_blobs_verified':3,'unchanged_phase_a_files_verified':4,'source_clean':True,'reverse_applicability':True,'source_reviewed':['core/qd_capture_dwell.py','core/rdt_policy_steer.py diff','main.py diff','configs/config.yaml diff','configs/qd_ed_final/candidate_n31.json','tests/test_n31_capture_dwell_integration.py','tests/n31_original_methods.json against base AST'],'delivery':ref(P/'delivery-manifest-phase-b-v1.json'),'report':ref(P/'cpu-phase-b-report-v1.md'),'compute_evidence':ref(P/'compute-evidence-phase-b-v1.json'),'resource_ledger':ref(P/'cpu-resource-ledger-phase-b-v1.json'),'receipts':receipts,'final_distinct_synthetic_cases':37,'all_six_guards_clean':True,'source_bound_final_run':ref(P/'cpu-phase-b-run6-source.json'),'aggregate_test_cpu_seconds':cpu,'aggregate_test_wall_seconds':wall,'root_reran_tests':False,'root_recomputed_scientific_tensors':False,'genuine_empty_provider_regression_fixed_and_failure_retained':True,'root_static_review_initial_receipt_key_error':'First metadata check assumed optional timeout key and stopped; corrected against real external receipt schema. No experiment/test/source modification resulted.','limitations':['Synthetic production paths are not actual model/GPU/robot evidence.','Independent native audit and runner/controller integration remain required.','Active BF16 final archive diagnostic cardinality can change; fixed primary/model/RBF/RNG counts do not imply fixed total diagnostic projection rows.','Two harmless EOF whitespace warnings retained to preserve tested bytes.','Approximate point prism and dwell do not establish capture or benefit.'],'score':'Unknown','target_achieved':False,'gpu_authorized':False}
assert not (P/'root-phase-b-review-v1.json').exists();r.durable_json(P/'root-phase-b-review-v1.json',review)
draft=(P/'cpu-phase-c-native-runtime-draft-v1.md').read_text()
body=draft.split('Required independent worker audit:',1)[1]
header=f"""# N31 CPU Phase C — native audit and runtime integration

Authorized by root after the independent phase-B acceptance at {now}.
Accepted source commit: {S['commit']}.
Preceding review: {P/'root-phase-b-review-v1.json'} SHA{ref(P/'root-phase-b-review-v1.json')['sha256']}.
Hypothesis: {P/'hypothesis-and-cpu-phase-a-v1.md'} SHA{ref(P/'hypothesis-and-cpu-phase-a-v1.md')['sha256']}.
Prospective Dev protocol: {P/'prospective-dev-science-protocol-v1.md'} SHA{ref(P/'prospective-dev-science-protocol-v1.md')['sha256']}.
Ten Dev identities: {P/'dev-task-identities-v1.json'} SHA{ref(P/'dev-task-identities-v1.json')['sha256']}.

Delegate only to existing /root/n22_cpu_executor. Work in {I}, branch codex/n31-capture-dwell. This release authorizes CPU implementation and bounded synthetic tests only. No source adoption into owning study, GPU/API/model/environment execution, new historical tensor/video measurements, active experiment controller, or budget change. Root owns operational state, budget, final integration and release. Preserve phase-A arithmetic and frozen algorithm choices; new correctness blockers must be reported with exact scope before an algorithm change. Phase B fixes and unsupported-provider behavior are accepted baseline.

"""
scope=P/'cpu-phase-c-native-runtime-v1.md';assert not scope.exists()
body=body.replace('Proposed CPU test allowance for eventual release:', 'Authorized cumulative CPU test allowance:').replace('if later created','(created for this phase)')
scope.write_text(header+'Required independent worker audit:'+body)
(P/'artifacts/cpu-phase-c-scratch').mkdir(exist_ok=False)
with r.locked(W/'data/qd-ed-state.lock'),a.state_lock(W,run):
 state=r.read_state(W/'research-state.yaml');cp=r.read_json(coord/'checkpoint.json');tree=a.load_tree(W,run)
 old=state['current_cpu_task'];assert old['phase']=='N31_CAPTURE_DWELL_CPU_PHASE_B' and old['node_id']=='15.1'
 assert state['current_owned_workers']==[] and state['active_plan'] is None and state['active_controller'] is None
 budget=copy.deepcopy(state['budget']);lex=state['worktree']
 snap=P/'phase-c-registration-before-v1';snap.mkdir(exist_ok=False)
 for n,obj in [('state',state),('checkpoint',cp),('tree',tree)]:r.durable_json(snap/(n+'.json'),obj)
 task={'status':'DISPATCHED','phase':'N31_CAPTURE_DWELL_CPU_PHASE_C','node_id':'15.1','agent':'/root/n22_cpu_executor','scope':ref(scope),'preceding_review':ref(P/'root-phase-b-review-v1.json'),'implementation_worktree':str(I),'branch':'codex/n31-capture-dwell','source_base':S['commit'],'test_cpu_seconds_limit':1200,'test_wall_seconds_limit':1800,'threads':2,'historical_tensor_or_video_reads_authorized':False,'new_exposed_data_measurements_authorized':False,'gpu_authorized':False,'production_hookup_authorized':True,'prospective_dev_protocol':ref(P/'prospective-dev-science-protocol-v1.md'),'dev_identity_plan':ref(P/'dev-task-identities-v1.json'),'storage_binding':ref(P/'artifact-storage-binding-v1.json'),'registered_at':now}
 state.update(current_cpu_task=task,next_action='Implement independent N31 native audit and disabled ten-task C0/Q0/N31 Dev plan/runner/worker/controller. Bounded CPU synthetic production-path tests only. No GPU release or budget adoption.',updated_at=now)
 state['active_iteration'].update(status='CPU_PHASE_C',source_base=S['commit'],phase_b_review=task['preceding_review'],execution_authorized=False,validation_authorized=False,formal_authorized=False,target_achieved=False)
 state['study']['status']='N31_CAPTURE_DWELL_CPU_PHASE_C_TARGET_NOT_MET'
 cp.update(status=state['study']['status'],phase='DISPATCH_CPU',in_flight_executor=task,in_flight_executors=[task],inflight_executor=task,inflight_executors=[task],executor_task=task,next_action=state['next_action'],automatic_gpu_dispatch_authorized=False,automatic_gpu_dispatch_scope=None,updated_at=now,goal_achieved=False,target_achieved=False,target_met=False)
 tree['meta'].update(study_status=state['study']['status'],target_achieved=False,automatic_dispatch_authorized=False)
 leaf=a.node(tree,'15.1');assert leaf['status']=='running';leaf.update(phase='CPU_PHASE_C',cpu_task=task,code_ref=S['commit'],phase_b_review=task['preceding_review'],gpu_execution_authorized=False,target_achieved=False)
 leaf['result']='Phase B source-bound37 synthetic integration tests pass; genuine empty-provider regression fixed and all failures preserved. Native audit/runtime implementation now authorized on CPU. Task efficacy Unknown.'
 assert state['budget']==budget and state['worktree']==lex
 tmp=W/'research-state.yaml.n31-phase-c-v1'
 with tmp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
 os.replace(tmp,W/'research-state.yaml');r.durable_json(coord/'checkpoint.json',cp);a.save_tree(W,run,tree)
 note=f"\n### {now} — N31 phase B accepted; CPU native/runtime integration\n\nRoot checked58 delivery/source file entries,25 Git source entries,3 base blobs,4 unchanged phase-A files, clean commit {S['commit']}, exact run6 source,6 reaped processes and guard-clean receipts. Final37 production-path synthetic cases pass; cumulative test CPU{cpu:.6f}s/wall{wall:.6f}s. Real empty-provider regression and prior failures preserved. Phase C scope: {scope}. CPU1200s/wall1800s cumulative,2threads; no GPU/API/simulation or budget change. Native audit and disabled full10 Dev runtime implementation only. Target NOT_MET.\n"
 for path in [session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md']:
  with path.open('a') as f:f.write(note)
 r.durable_json(P/'root-cpu-phase-c-registration-v1.json',{'task':task,'budget_changed':False,'previous_task':old})
print(json.dumps({'review':ref(P/'root-phase-b-review-v1.json'),'task':task['phase'],'scope':task['scope']}))

