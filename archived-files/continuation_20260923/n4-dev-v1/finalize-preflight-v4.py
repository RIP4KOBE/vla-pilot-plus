import copy,datetime,json,os,pathlib,sys,time
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
W=pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z');B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(W/'scripts'));import qd_ed_final_runner as r;import qd_ed_n4_plan as n;import qd_ed_n4_supervise as supervisor
ref=lambda p:{'path':str(pathlib.Path(p).resolve()),'sha256':r.digest(p)}
def write(name,value):
 with (B/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
plan,manifest,runtime=r.validate_plan(B/'plan.unfrozen.json',root=W,require_frozen=False)
preview=r.read_json(B/'resolved-override-preview.json');resource=r.read_json(B/'resource-preflight.json')
assert preview['source_commit']==plan['source_commit'] and preview['source_files_sha256']==n.source_identity(plan)
assert preview['draft']==ref(B/'plan.unfrozen.json') and preview['CPU_composition_passed'] is True and preview['cuda_initialized'] is False
assert len(preview['rows'])==12 and [x['row'] for x in preview['rows']]==plan['episodes']
for row in preview['rows']:
 command,_=r.build_command(plan,manifest,runtime,row['row'],'PREVIEW__'+row['episode_key']);assert command==row['command']
assert 'torch' not in sys.modules or not sys.modules['torch'].cuda.is_initialized()
supervisor.prerequisite(r,n,plan,runtime,W)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
 events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl');state=r.read_state(W/'research-state.yaml')
 r.check_budget(state,events,plan['episodes'][0],resources);n.protected_budget(state,events,resources,plan['episodes'][0],1800,r,plan=plan);n.admission(plan,runtime,plan['episodes'][0],events,resources,W,r)
 budget=r.budget_snapshot(events,resources)
assert budget==resource['budget'] and budget['running']==0
child=r.child_environment(runtime);public_env={key:child[key] for key in ['CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','MUJOCO_GL','PYOPENGL_PLATFORM','CUDA_DEVICE_ORDER','JOBLIB_MULTIPROCESSING']}
assert public_env['CUDA_VISIBLE_DEVICES']=='3' and public_env['MUJOCO_EGL_DEVICE_ID']=='0'
correction={'schema':'n4-preflight-finalization-correction-v1','reason':'v3 completed all12 CPU compositions and resource/native dependency preflight, then root index construction mistakenly expected CUDA keys under runtime.environment. Actual unmodified runner injects those keys from frozen gpu_mapping in child_environment. Continue from preserved exact previews; do not rerun successful composition or alter scientific/runtime code. No prior frozen plan or execution release existed.','prior_process':ref(B/'preparation-v3-process.json'),'previous_script':ref(B/'prepare-and-freeze-v3.py'),'continuation_script':ref(__file__),'GPU_dispatches':0,'scientific_identity_unchanged':True}
write('preparation-v4-correction.json',correction)
index={'schema':'qd-ed-n4-preflight-index-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':plan['source_commit'],'draft':ref(B/'plan.unfrozen.json'),'preview':ref(B/'resolved-override-preview.json'),'resources':ref(B/'resource-preflight.json'),'CPU_composition_passed':True,'GPU_dispatches':0,'models_loaded':False,'provider_calls':0,'rows':[x['episode_key'] for x in plan['episodes']],'runtime_environment':public_env,'root_preparation_script':ref(__file__),'preserved_correction':ref(B/'preparation-v4-correction.json')}
write('preflight-index.json',index)
frozen=copy.deepcopy(plan);frozen.update(frozen=True,frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),preflight_index=str(B/'preflight-index.json'),preflight_index_sha256=r.digest(B/'preflight-index.json'))
write('plan.frozen.json',frozen)
start=time.monotonic();r.validate_plan(B/'plan.frozen.json',root=W,require_frozen=True)
result={'schema':'qd-ed-n4-frozen-validation-v1','status':'PASS','frozen_plan':ref(B/'plan.frozen.json'),'source_commit':plan['source_commit'],'actual_model_input_source_hashes_verified':True,'full_validation_seconds':time.monotonic()-start,'episodes':12,'GPU_dispatches':0,'provider_calls':0,'execution_release_created':False,'scientific_promotion':False,'cuda_initialized':False}
assert 'torch' not in sys.modules or not sys.modules['torch'].cuda.is_initialized()
write('frozen-validation.json',result)
print(json.dumps(result));print(json.dumps({'budget':budget,'candidate_delta':preview['candidate_delta'],'child_environment':public_env}))
