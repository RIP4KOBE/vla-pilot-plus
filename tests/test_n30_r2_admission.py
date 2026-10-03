"""Complete pure plan/command path with synthetic runtime/state and closed authority mocks."""
import copy,json
from pathlib import Path
import pytest
from scripts import qd_ed_final_runner as r,qd_ed_n30_r2_contract as c,qd_ed_n23_worker as w
from n30_r2_synthetic import rows,write

@pytest.fixture
def frozen(tmp_path,monkeypatch):
    root=tmp_path/'owning';root.mkdir();globalroot=tmp_path/'global';globalroot.mkdir();variant=tmp_path/'variants/n30_executed_progress_continuation';variant.mkdir(parents=True)
    target=globalroot/'variants/n30_executed_progress_continuation';target.mkdir(parents=True);(variant/'artifacts').symlink_to(target,target_is_directory=True)
    (tmp_path/'artifacts').symlink_to(globalroot,target_is_directory=True)
    monkeypatch.setattr(c,'RUN_DIR',variant/'feedback-repair-continuation-v1');monkeypatch.setattr(c,'ARTIFACT_DIR',variant/'artifacts');monkeypatch.setattr(c,'SESSION',tmp_path)
    rr=rows();task_inputs=[];tasks={};seedrows=[]
    for t in range(4):
        init=globalroot/f'init{t}';bddl=globalroot/f'bddl{t}';init.write_text('init');bddl.write_text('bddl')
        seed={'task_id':t,'env_seed':11+t,'policy_seed':22+t,'init_index':0,'init_row_sha256':'a'*64,'init_file_sha256':w.sha(init),'bddl_sha256':w.sha(bddl)}
        for row in rr[t*3:t*3+3]:row.update({k:v for k,v in seed.items() if k!='task_id'})
        seedrows.append(seed);tasks[str(t)]={'init_index':0,'init_path':str(init),'bddl_path':str(bddl),'cache_dir':str(globalroot/f'cache{t}')}
        task_inputs.append({'task_id':t,'used_init_index':0,'used_init_row_sha256':'a'*64})
    rr=rr[2:];rr[0].update(budget_bucket='recovery',retry_of=c.b.FAILED)
    for row in rr:row['original_episode_key']=row['episode_key'].replace('n30_r2_dev_','n30_dev_')
    provider={'backend':'codex_cli','model':'gpt-6-astra','auth_mode':'chatgpt','reasoning_effort':'low','timeout_seconds':180,
      'cli_path':str(tmp_path/'codex'),'cli_version':'0.155.1','cli_sha256':'a'*64,'disabled_skill_paths':[str(tmp_path/'disabled')],'allow_recovered_error_events':True}
    provider['public_config_sha256']=r.codex_public_config_sha256(provider)
    rt={'schema':'qd-ed-runtime-setup-v1','worktree':str(root),'artifact_root':str(globalroot),'tasks':tasks,'files':[{'path':str(globalroot/'init0'),'sha256':w.sha(globalroot/'init0')}],
      'environment':{'LIBERO_CONFIG_PATH':str(globalroot/'libero')},'main_overrides':['+main.require_task_cache_identity=true'],
      'frozen_stage_provider':provider,'stage_engineering_condition':r.n4e1_support().engineering_condition(),
      'stage_recovered_error_condition':r.E2_STAGE_CONDITION,'provider_ready':True,'cuda_egl_verified':True,
      'cuda_egl_probe':{'resource_id':c.GPU7_PROOF},'gpu_mapping':{'physical_gpu':7,'uuid':c.GPU7_UUID,'egl_device_index':4}}
    rtref=write(globalroot/'runtime.json',rt);monkeypatch.setattr(c,'runtime_ref',lambda *a:rtref)
    # Pure JSON input reads are synthetic; only source/profile reads use the actual isolated worktree.
    seeds={'schema':'qd-ed-frozen-seed-plan-v1','run_name':'CPU','blocks':{'dev':seedrows}}
    inventory={'schema':'qd-ed-runtime-inventory-v1','checkpoint':[{'path':str(globalroot/'init0'),'sha256':w.sha(globalroot/'init0')}],'hf_encoders':[],'dinov2':{'weights':{'path':str(globalroot/'init0'),'sha256':w.sha(globalroot/'init0')}},'libero_tasks':task_inputs}
    inventory_path=root/'configs/n30-synthetic-inventory.json';seed_path=root/'configs/n30-synthetic-seeds.json'
    read=r.read_json;digest=r.digest
    monkeypatch.setattr(r,'read_json',lambda path:copy.deepcopy(inventory if Path(path)==inventory_path else seeds if Path(path)==seed_path else read(path)))
    monkeypatch.setattr(r,'digest',lambda path:'s'*64 if Path(path) in {inventory_path,seed_path} else digest(path))
    paths=r.REQUIRED_CODE|w.REQUIRED_SOURCE|{'configs/qd_ed_final/candidate_n30.json','configs/qd_ed_final/n4_observed_baseline_profiles.json'}
    for name in paths:
        target_file=root/name;target_file.parent.mkdir(parents=True,exist_ok=True);target_file.write_bytes(b'synthetic-source')
    for name in ('candidate_n30.json','n4_observed_baseline_profiles.json'):
        (root/'configs/qd_ed_final'/name).write_bytes((r.ROOT/'configs/qd_ed_final'/name).read_bytes())
    monkeypatch.setattr(c,'source_paths',lambda _:paths)
    monkeypatch.setattr(c,'imports_owned',lambda got,env:None)  # module/source ownership is a separate byte-bridge check
    profile=root/'configs/qd_ed_final/n4_observed_baseline_profiles.json'
    source={'commit':'CPU-HEAD','files':[{'path':p,'sha256':w.sha(root/p)} for p in sorted(paths)],'sha256':'synthetic'}
    monkeypatch.setattr(w,'source_record',lambda got,paths:source)
    monkeypatch.setattr(r.subprocess,'check_output',lambda *a,**k:'CPU-HEAD\n')
    st={'run_name':'CPU','artifacts':str(globalroot),'worktree':str(root),'gpu_pool':[7],'max_concurrent_gpu_workers':1}
    monkeypatch.setattr(r,'read_state',lambda _:st)
    marker={'worker_audit':c.WORKER_CONTRACT};calls=[]
    monkeypatch.setattr(c,'metadata',lambda *a:marker);monkeypatch.setattr(c,'expected_rows',lambda *a:rr);monkeypatch.setattr(c,'history',lambda:{})
    monkeypatch.setattr(c,'require_state',lambda *a:calls.append('adopted_authority'))
    plan={'schema':r.SCHEMA,'frozen':True,'worktree':str(root),'run_name':'CPU','artifact_root':str(target),
      'source_commit':'CPU-HEAD','code_files':source['files'],'scientific_config_files':['configs/qd_ed_final/candidate_n30.json'],
      'profiles_path':str(profile),'profiles_sha256':w.sha(profile),'candidate_profiles':{a:c.ref(root/f'configs/qd_ed_final/candidate_{a.lower()}.json') for a in ('N30',)},
      'runtime_manifest_path':rtref['path'],'runtime_manifest_sha256':rtref['sha256'],'runtime_inventory_path':str(inventory_path),'runtime_inventory_sha256':'s'*64,
      'seed_plan_path':str(seed_path),'seed_plan_sha256':'s'*64,'episodes':rr,'n30_r2_cohort':marker,'egl_mapping_verified':True,
      'phase_authorization':{'dev':True,'validation':False,'formal':False},'stage_condition':r.E2_STAGE_CONDITION,'input_contract_label':'input_repaired'}
    path=tmp_path/'plan.json';write(path,plan)
    return path,plan,rt,st,calls


def test_complete_runner_validate_and_all_three_real_hydra_commands(frozen):
    from hydra import compose,initialize_config_dir
    from omegaconf import OmegaConf
    path,plan,rt,st,calls=frozen
    actual,manifest,runtime=r.validate_plan(path,root=Path(plan['worktree']))
    assert actual==plan and runtime==rt and calls==['adopted_authority']
    with initialize_config_dir(config_dir=str(r.ROOT/'configs'),version_base=None):
        for row in plan['episodes'][:3]:
            command,output=r.build_command(plan,manifest,runtime,row,'CPU-'+row['profile'])
            config=OmegaConf.to_container(compose(config_name='config',overrides=command[2:]),resolve=False)
            assert output==Path(plan['artifact_root'])/'attempts'/('CPU-'+row['profile'])
            assert config['main']['eds_config']['rollout_diversity_placement']=='model_output'
            assert config['main']['eds_config']['diversity_update_mode']=='legacy_additive'
            assert config['main']['eds_config']['executed_progress_continuation_mode']==('executed_progress_continuation_v1' if row['profile']=='N30' else 'off')
            assert config['main']['eds_config']['executed_progress_continuation_control']=='none'
            for expected in ('perception.gemini.backend=codex_cli','perception.gemini.model=gpt-6-astra','perception.gemini.timeout_seconds=180','perception.gemini.reasoning_effort=low'):assert expected in command
            assert not any('api_key=' in v or 'base_url=' in v for v in command)
    assert runtime['frozen_stage_provider']['auth_mode']=='chatgpt'

@pytest.mark.parametrize('fault',['escaped_artifact','global_attempt_root','runtime_subroot','mixed_marker','r1_marker','seed','profile','authority','source'])
def test_complete_admission_rejects_boundary_mismatch(frozen,monkeypatch,fault):
    path,p,rt,st,calls=frozen
    if fault=='escaped_artifact':p['artifact_root']=str(path.parent/'escape')
    elif fault=='global_attempt_root':p['artifact_root']=st['artifacts']
    elif fault=='runtime_subroot':
        rt['artifact_root']=p['artifact_root'];write(p['runtime_manifest_path'],rt);p['runtime_manifest_sha256']=w.sha(p['runtime_manifest_path'])
    elif fault=='mixed_marker':p['n28_cohort']={}
    elif fault=='r1_marker':p['n30_r1_cohort']={}
    elif fault=='seed':p['episodes'][0]['env_seed']+=1
    elif fault=='profile':p['candidate_profiles']['N30']['sha256']='b'*64
    elif fault=='authority':monkeypatch.setattr(c,'require_state',lambda *a:(_ for _ in ()).throw(ValueError('no root adoption')))
    elif fault=='source':p['source_commit']='other'
    write(path,p)
    with pytest.raises((ValueError,r.GateError)):r.validate_plan(path,root=Path(p['worktree']))


def test_missing_authority_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setattr(c,'AUTHORITY',tmp_path/'authority.json')
    with pytest.raises(OSError):c.authority({}, {}, tmp_path)
