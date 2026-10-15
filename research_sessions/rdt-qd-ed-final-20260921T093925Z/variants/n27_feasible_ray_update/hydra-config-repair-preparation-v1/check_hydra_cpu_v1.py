"""Real Hydra composition of source-extracted original pure command builders."""
import ast,builtins,copy,hashlib,json,re,sys,time,types
from pathlib import Path
HERE=Path(__file__).absolute().parent
INDEX=json.loads((HERE/'static-inputs-v1.json').read_text())
SOURCE={}
for entry in INDEX['files']:
    b=Path(entry['path']).read_bytes();assert hashlib.sha256(b).hexdigest()==entry['sha256']
    SOURCE[entry['relative_path']]=b
ROOT=Path(INDEX['files'][0]['path']).parents[1]
def read_json(path):
    name=str(Path(path).relative_to(ROOT));assert name.startswith('configs/qd_ed_final/');return json.loads(SOURCE[name])
def digest(path):return hashlib.sha256(SOURCE[str(Path(path).relative_to(ROOT))]).hexdigest()
def extract(path,names,env,assign=False):
    tree=ast.parse(SOURCE[path],filename=path)
    chosen=[n for n in tree.body if (isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names) or
     (assign and isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in names for t in n.targets))]
    found={n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id for n in chosen};assert found==set(names),(path,set(names)-found)
    exec(compile(ast.Module(body=chosen,type_ignores=[]),path,'exec'),env)
    return [{'file':path,'name':n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id,'first_line':n.lineno,'last_line':n.end_lineno} for n in chosen]

functions=[];modules={};original_import=builtins.__import__
def pure_import(name,globals=None,locals=None,fromlist=(),level=0):
    if name=='scripts':
        assert set(fromlist)<=set(modules),fromlist
        return types.SimpleNamespace(**modules)
    raise ImportError('source AST attempted unapproved import: '+name)
env={'__builtins__':dict(vars(builtins),__import__=pure_import),'Path':Path,'json':json,'copy':copy,'re':re,
 'hashlib':hashlib,'ROOT':ROOT,'PYTHON':Path(sys.executable),'read_json':read_json,'digest':digest}
runner='scripts/qd_ed_final_runner.py'
functions+=extract(runner,('CODEX_CONFIG_KEYS','E2_STAGE_CONDITION','CODEX_STAGE_CONDITION'),env,True)
functions+=extract(runner,('GateError','require','owned','hydra','expand_candidate','is_n17_plan','stage_condition','codex_public_config','codex_public_config_sha256','stage_overrides','build_command'),env)
policy={'Path':Path,'json':json,'hashlib':hashlib}
functions+=extract('core/codex_stage_policy.py',('_DISABLED_FEATURES','_DEVELOPER_INSTRUCTIONS'),policy,True)
functions+=extract('core/codex_stage_policy.py',('public_invocation_policy','policy_sha256'),policy)
env['codex_policy_module']=lambda:types.SimpleNamespace(**policy)
engineering={}
functions+=extract('scripts/qd_ed_n4e1_plan.py',('ORIGINAL_PROTOCOL','PROTOCOL','PREREQUISITE','FROZEN_DOCS','CONDITION_ID','STAGE_CONDITION'),engineering,True)
functions+=extract('scripts/qd_ed_n4e1_plan.py',('engineering_condition',),engineering)
env['n4e1_support']=lambda:types.SimpleNamespace(**engineering)
geometry={};clean={};helper={}
functions+=extract('core/qd_actuator_clipped_rbf.py',('MODE',),geometry,True)
functions+=extract('core/qd_clean_output_rbf.py',('CLEAN_SOURCE',),clean,True)
functions+=extract('core/qd_feasible_ray_rbf.py',('LEGACY','MODE'),helper,True)
helper.update(GEOMETRY=geometry['MODE'],CLEAN_SOURCE=clean['CLEAN_SOURCE'])
functions+=extract('core/qd_feasible_ray_rbf.py',('validate_update_option',),helper)
for number in (25,26,27):
    ns={'Path':Path,'copy':copy,'w':types.SimpleNamespace(require=env['require'],sha=digest),'native':types.SimpleNamespace(MODE=geometry['MODE'])}
    functions+=extract(f'scripts/qd_ed_n{number}_contract.py',('expand_candidate',),ns)
    modules[f'qd_ed_n{number}_contract']=types.SimpleNamespace(**ns)

# Actual Hydra/OmegaConf, no production module or main decorator executed.
from hydra import initialize_config_dir,compose
from hydra.errors import ConfigCompositionException
from omegaconf import OmegaConf
from importlib.metadata import version
base=read_json(ROOT/'configs/qd_ed_final/baseline_profiles.json')
profiles=copy.deepcopy(base['profiles'])
for arm in ('N26','N27'):profiles[arm]=env['expand_candidate'](arm,read_json(ROOT/f'configs/qd_ed_final/candidate_{arm.lower()}.json'),base['profiles']['Q0'])
assert helper['LEGACY']=='legacy_additive' and helper['MODE']=='feasible_ray_v1'
assert profiles['N27']['resolved_eds_config']=={**profiles['N26']['resolved_eds_config'],'diversity_update_mode':helper['MODE']}
frozen={'backend':'codex_cli','auth_mode':'chatgpt','model':'gpt-6-astra','reasoning_effort':'low','timeout_seconds':180,
 'cli_path':str(HERE/'synthetic/codex'),'cli_version':'0.155.1','cli_sha256':'0'*64,'disabled_skill_paths':[str(HERE/'synthetic/disabled-skill')],'allow_recovered_error_events':True}
frozen['public_config_sha256']=env['codex_public_config_sha256'](frozen)
runtime={'frozen_stage_provider':frozen,'stage_engineering_condition':engineering['engineering_condition'](),
 'stage_recovered_error_condition':env['E2_STAGE_CONDITION'],'tasks':{'0':{'cache_dir':str(HERE/'synthetic/cache')}},'main_overrides':['+main.require_task_cache_identity=true']}
plan={'worktree':str(ROOT),'artifact_root':str(HERE/'synthetic/artifacts')}
results=[];full=[];checks=[];before_configs={};after_configs={}
def compose_one(kind,argv):
    with initialize_config_dir(version_base=None,config_dir=str(HERE/kind/'configs')):
        cfg=compose(config_name='config',overrides=argv[2:])
        raw=OmegaConf.to_container(cfg,resolve=False)
        eds=OmegaConf.to_container(cfg.main.eds_config,resolve=True) # No interpolations exist in this subtree.
        assert not any('${' in str(v) for v in eds.values())
        return raw,eds
for arm in ('C0','Q0','N26','N27'):
    row={'profile':arm,'policy_seed':101,'env_seed':202,'task_id':0};argv,output=env['build_command'](plan,{'profiles':profiles},runtime,row,'synthetic_'+arm)
    assert argv[:2]==[sys.executable,str(ROOT/'main.py')]
    assert all(not s.startswith(('perception.gemini.api_key=','perception.gemini.base_url=')) for s in argv[2:])
    full.append({'arm':arm,'argv':argv,'synthetic_only':True,'executed':False})
    try:
        raw,eds=compose_one('original',argv)
        assert arm!='N27','unmodified N27 unexpectedly composed'
        before_configs[arm]=(raw,eds);results.append({'arm':arm,'tree':'original','composed':True})
    except ConfigCompositionException as exc:
        assert arm=='N27' and "main.eds_config.diversity_update_mode" in str(exc)
        results.append({'arm':arm,'tree':'original','composed':False,'expected_hydra_error':str(exc)})
    raw,eds=compose_one('patched',argv);after_configs[arm]=(raw,eds)
    assert eds['diversity_update_mode']==(helper['MODE'] if arm=='N27' else helper['LEGACY'])
    helper['validate_update_option'](types.SimpleNamespace(**eds))
    results.append({'arm':arm,'tree':'patched','composed':True,'update_mode':eds['diversity_update_mode']})
    if arm!='N27':
        control_raw=copy.deepcopy(raw);control_raw['main']['eds_config'].pop('diversity_update_mode')
        control_eds=copy.deepcopy(eds);control_eds.pop('diversity_update_mode')
        assert control_raw==before_configs[arm][0] and control_eds==before_configs[arm][1]
        helper['validate_update_option'](types.SimpleNamespace(**before_configs[arm][1]))
        checks.append(arm+'_whole_composed_and_resolved_EDS_parity_except_registered_disabled_key')
assert after_configs['N27'][1]=={**after_configs['N26'][1],'diversity_update_mode':helper['MODE']}
checks.append('N27_vs_N26_sole_resolved_EDS_delta_feasible_ray_v1')
# Disabled spelling and active config drift are independently rejected by actual source predicate.
for mutate in ({'diversity_update_mode':'none'},{'diversity_update_mode':'unknown'},{'population_size':15}):
    try:helper['validate_update_option'](types.SimpleNamespace(**(after_configs['N27'][1]|mutate)))
    except ValueError:checks.append('predicate_rejects_'+next(iter(mutate))+'_'+str(next(iter(mutate.values()))))
    else:raise AssertionError('required source predicate failed to reject '+str(mutate))
# Hydra must still reject misspellings, not silently append arbitrary schema keys.
bad=full[-1]['argv']+['main.eds_config.not_a_registered_option=true']
try:compose_one('patched',bad)
except ConfigCompositionException:checks.append('unknown_struct_key_still_rejected')
else:raise AssertionError('struct validation bypassed')
assert not any(n=='main' or n=='torch' or n.startswith(('core.','scripts.','robosuite','libero')) for n in sys.modules)
result={'schema':'n27-hydra-repair-cpu-result-v1','synthetic_only':True,'hydra_version':version('hydra-core'),'omegaconf_version':version('omegaconf'),
 'source_commit':'095cfeecd6af55477d2529441c307ab712e8a8da','compositions':results,'checks':checks,'ast_functions':functions,
 'complete_argv_count':4,'model_api_sim_gpu_calls':0,'torch_imported':False,'main_imported':False,'production_modules_imported':False,
 'dynamic_resolution':'No custom resolver registered/executed. Full config structural comparison uses resolve=False; interpolation-free EDS uses resolve=True.',
 'actual_runtime_metadata_read':False,'source_adoption_authorized':False,'experiment_restart_authorized':False}
(HERE/'cpu-result-v1.json').write_text(json.dumps(result,indent=2)+'\n')
(HERE/'synthetic-build-command-argv-v1.json').write_text(json.dumps(full,indent=2)+'\n')
print(json.dumps({'compositions':len(results),'patched_pass':sum(v['tree']=='patched' and v['composed'] for v in results),'expected_old_N27_failure':1,'checks':len(checks),'torch_imported':False}))
