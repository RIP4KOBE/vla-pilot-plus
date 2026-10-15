import copy, datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, time
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
W=pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
B=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(W/'scripts'))
import qd_ed_final_runner as r
import qd_ed_n4_plan as n
import qd_ed_n4_supervise as supervisor
from hydra import compose, initialize_config_dir
from hydra.core.override_parser.overrides_parser import OverridesParser
from omegaconf import OmegaConf
ref=lambda p:{'path':str(pathlib.Path(p).resolve()),'sha256':r.digest(p)}
def write(name,value):
    with (B/name).open('x') as f: json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')
draft=B/'plan.unfrozen.json'
plan,manifest,runtime=r.validate_plan(draft,root=W,require_frozen=False)
rows=[];effective={}
for row in plan['episodes']:
    command,_=r.build_command(plan,manifest,runtime,row,'PREVIEW__'+row['episode_key'])
    overrides=command[2:]
    with initialize_config_dir(version_base=None,config_dir=str(W/'configs')):
        cfg=compose(config_name='config',overrides=overrides,return_hydra_config=True)
    named={}
    for override in OverridesParser.create().parse_overrides(overrides):
        key=override.key_or_group;expected=override.value()
        if key=='backend':
            assert expected=='libero';named[key]=expected;continue
        value=OmegaConf.select(cfg,key)
        if OmegaConf.is_config(value): value=OmegaConf.to_container(value,resolve=True)
        assert value==expected, (row['episode_key'],key)
        named[key]=value
    eds=OmegaConf.to_container(cfg.main.eds_config,resolve=True)
    expected_mode='terminal_population_v1' if row['profile']=='N4' else 'archive_global_best'
    assert eds['qd_final_selection_mode']==expected_mode
    assert eds['qd_quality_mode']=='provider' and eds['population_size']==16 and eds['cem_iters']==10
    assert cfg.policy.rdt.action_chunk_horizon==8 and cfg.policy.rdt.control_frequency==20
    assert cfg.main.max_episode_steps==720 and cfg.backend.libero.strict_perturbations
    assert cfg.main.decision_evidence.enabled and cfg.seed==row['policy_seed']
    assert list(cfg.main.episode_seed_schedule)==[row['env_seed']]
    effective[row['profile']]=eds
    rows.append({'episode_key':row['episode_key'],'row':row,'command':command,'resolved_named_overrides':named,'resolved_final_selection_mode':expected_mode,'resolved_quality_mode':eds['qd_quality_mode']})
changed={key:{'before':effective['Q0'].get(key),'after':effective['N4'].get(key)} for key in effective['Q0'].keys()|effective['N4'].keys() if effective['Q0'].get(key)!=effective['N4'].get(key)}
assert changed=={'qd_final_selection_mode':{'before':'archive_global_best','after':'terminal_population_v1'}},changed
assert not any(name in sys.modules for name in ['torch','mujoco','robosuite','main'])
preview={'schema':'qd-ed-n4-resolved-override-preview-v1','draft':ref(draft),'source_commit':plan['source_commit'],'source_files_sha256':n.source_identity(plan),'runtime_manifest_sha256':plan['runtime_manifest_sha256'],'seed_plan_sha256':plan['seed_plan_sha256'],'candidate_delta':changed,'rows':rows,'CPU_composition_passed':True,'GPU_dispatches':0,'models_loaded':False,'provider_calls':0,'cuda_visible_devices':'','heavy_imports':[]}
write('resolved-override-preview.json',preview)
supervisor.prerequisite(r,n,plan,runtime,W)
with r.locked(W/'data/qd-ed-runner.lock',nonblocking=True):
    events=r.read_events(W/'data/attempt-ledger.jsonl');resources=r.read_events(W/'data/gpu-healthcheck-ledger.jsonl');state=r.read_state(W/'research-state.yaml')
    r.check_budget(state,events,plan['episodes'][0],resources)
    n.protected_budget(state,events,resources,plan['episodes'][0],1800,r,plan=plan)
    n.admission(plan,runtime,plan['episodes'][0],events,resources,W,r)
    budget=r.budget_snapshot(events,resources)
assert budget['running']==0
resource={'schema':'qd-ed-n4-predispatch-resource-snapshot-v1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'budget':budget,'artifact_free_bytes':shutil.disk_usage(B).free,'worktree_free_bytes':shutil.disk_usage(W).free,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'local_originals':12,'baseline_originals':6,'development_originals':6,'max_dispatches':16,'protected_validation_formal_attempts':100,'protected_validation_formal_hours':24,'new_health_dispatches':0,'reused_health_resources':plan['n4_cohort']['health_resources']}
write('resource-preflight.json',resource)
index={'schema':'qd-ed-n4-preflight-index-v1','reviewed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':plan['source_commit'],'draft':ref(draft),'preview':ref(B/'resolved-override-preview.json'),'resources':ref(B/'resource-preflight.json'),'CPU_composition_passed':True,'GPU_dispatches':0,'models_loaded':False,'provider_calls':0,'rows':[x['episode_key'] for x in plan['episodes']],'runtime_environment':{k:runtime['environment'][k] for k in ['CUDA_VISIBLE_DEVICES','MUJOCO_EGL_DEVICE_ID','MUJOCO_GL','PYOPENGL_PLATFORM','CUDA_DEVICE_ORDER','JOBLIB_MULTIPROCESSING']},'root_preparation_script':ref(__file__)}
write('preflight-index.json',index)
frozen=copy.deepcopy(plan);frozen.update(frozen=True,frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),preflight_index=str(B/'preflight-index.json'),preflight_index_sha256=r.digest(B/'preflight-index.json'))
write('plan.frozen.json',frozen)
start=time.monotonic();r.validate_plan(B/'plan.frozen.json',root=W,require_frozen=True)
result={'schema':'qd-ed-n4-frozen-validation-v1','status':'PASS','frozen_plan':ref(B/'plan.frozen.json'),'source_commit':plan['source_commit'],'actual_model_input_source_hashes_verified':True,'full_validation_seconds':time.monotonic()-start,'episodes':12,'GPU_dispatches':0,'provider_calls':0,'execution_release_created':False,'scientific_promotion':False}
write('frozen-validation.json',result)
print(json.dumps(result));print(json.dumps({'budget':budget,'candidate_delta':changed}))
